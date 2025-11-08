from utils.logger import Logger
import pandas as pd
import asyncio
from datetime import datetime, time, timezone
import traceback

from strategies.BaseStrategy import BaseStrategy
from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.signal_repository import SignalRepository

from contracts.signal_contract import ValidatedSignal

logger = Logger.get_logger(__name__)


class BTC_Daily_Open_Strategy(BaseStrategy):
    """
    Estrategia basada en el precio de apertura diario de Bitcoin.
    VERSIÓN CORREGIDA - Bugs críticos solucionados
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        run_db_id: int | None = None,
        entry_threshold: float = -1.0,
        exit_threshold: float = 2.0,
        position_size_percent: float = 100.0,
        base_capital: float = 10.0,
        symbol: str = "BTCUSDT",
    ):
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size_percent = position_size_percent
        self.base_capital = base_capital
        self.symbol = symbol

        # Estado de la estrategia
        self.daily_open_price = None
        self.daily_open_time = None
        self.position_open = False
        self.entry_price = None
        self.entry_time = None
        self.current_price = None
        self.last_pnl_notification = None
        self.last_open_check_date = None

        self.rest_client = BinanceRESTClient(testnet=False)

    def _request_for_init(self, symbols: list[str]):
        try:
            logger.info(f"🔍 Solicitando datos diarios para {self.symbol}...")

            # Obtener velas diarias
            response = self.rest_client.get_all_klines(
                list_symbols=[self.symbol], interval="1d", limit=5
            )

            # Asignar Capital Inicial (Reglas de la estrategia)
            self.base_capital = self.rest_client.get_usdt_balance()

            logger.debug(f"Respuesta de API recibida: {response}")

            if self.symbol not in response or len(response[self.symbol]) == 0:
                logger.error(f"❌ No se encontraron datos diarios para {self.symbol}")
                self._fallback_to_ticker_price()
                return

            daily_candles = response[self.symbol]
            last_daily = daily_candles[-1]

            # 🔧 CORREGIDO: Validación explícita de tipo
            open_price = None
            open_timestamp = None

            # Formato LISTA (de REST API formateado)
            if isinstance(last_daily, (list, tuple)):
                if len(last_daily) >= 4:
                    # Formato: [symbol, open_time, close_time, open, close, high, low, volume]
                    try:
                        open_price = float(last_daily[3])  # Índice 3 = open
                        open_timestamp = (
                            int(last_daily[1]) / 1000
                        )  # Índice 1 = open_time
                    except (ValueError, TypeError, IndexError) as e:
                        logger.error(f"Error extrayendo de lista: {e}")

            # Formato DICCIONARIO (fallback si API cambia)
            elif isinstance(last_daily, dict):
                open_keys = ["open", "o", "openPrice", "open_price"]
                time_keys = ["open_time", "openTime", "timestamp", "t"]

                for key in open_keys:
                    if key in last_daily and last_daily[key] is not None:
                        try:
                            open_price = float(last_daily[key])
                            break
                        except (ValueError, TypeError):
                            continue

                for key in time_keys:
                    if key in last_daily and last_daily[key] is not None:
                        try:
                            open_timestamp = int(last_daily[key]) / 1000
                            break
                        except (ValueError, TypeError):
                            continue

            # Validar resultados
            if open_price is None or open_price <= 0:
                logger.error(f"❌ Precio de apertura inválido: {open_price}")
                self._fallback_to_ticker_price()
                return

            if open_timestamp is None:
                logger.warning("⚠️ Timestamp no disponible, usando hora actual")
                open_timestamp = datetime.now(timezone.utc).timestamp()

            # Asignar valores validados
            self.daily_open_price = open_price
            self.daily_open_time = datetime.fromtimestamp(
                open_timestamp, tz=timezone.utc
            )
            self.last_open_check_date = self.daily_open_time.date()

            logger.info(
                f"✅ Precio de apertura diario cargado: {self.daily_open_price:.2f} "
                f"({self.daily_open_time.strftime('%Y-%m-%d %H:%M UTC')})"
            )

            self._check_existing_position()

        except Exception as e:
            logger.error(f"❌ Error crítico cargando precio de apertura: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._fallback_to_ticker_price()

    def _fallback_to_ticker_price(self):
        """
        🔧 CORREGIDO: Fallback simplificado y robusto
        Usa ticker directo de Binance (más confiable que klines)
        """
        try:
            logger.info("🔄 Ejecutando fallback con ticker de Binance...")

            # Usar método directo del cliente Binance
            ticker = self.rest_client.client.get_symbol_ticker(symbol=self.symbol)
            current_price = float(ticker["price"])

            if current_price <= 0:
                raise ValueError(f"Precio ticker inválido: {current_price}")

            self.daily_open_price = current_price
            self.daily_open_time = datetime.now(timezone.utc)
            self.last_open_check_date = self.daily_open_time.date()

            logger.info(
                f"✅ Fallback exitoso - Usando precio ticker: {current_price:.2f}"
            )

        except Exception as e:
            logger.critical(f"💥 FALLBACK CRÍTICO FALLÓ: {e}")
            logger.critical(
                "🚨 No se puede iniciar estrategia sin precio de referencia"
            )
            raise RuntimeError(
                f"No se pudo obtener precio inicial para {self.symbol}. "
                "Verifica conexión a internet y validez del símbolo."
            )

    def _check_existing_position(self):
        """Verificar si ya existe una posición abierta."""
        self.position_open = False
        self.entry_price = None
        self.entry_time = None

    async def _handle_update(self, last_candles: dict):
        if self.symbol not in last_candles:
            return

        try:
            kline = last_candles[self.symbol]

            close_price = self._extract_close_price(kline)
            if close_price is None or close_price <= 0:
                logger.warning(f"⚠️ Precio de cierre inválido: {close_price}")
                return

            self.current_price = close_price
            current_time = datetime.now(timezone.utc)

            # Validar que tenemos precio de apertura
            if self.daily_open_price is None or self.daily_open_price <= 0:
                logger.warning("⚠️ Precio de apertura no disponible, reinicializando...")
                self.daily_open_price = close_price
                self.daily_open_time = current_time
                self.last_open_check_date = current_time.date()
                return

            # Verificar nuevo día
            await self._check_and_update_daily_open(current_time)

            # Calcular cambio porcentual
            price_change_pct = (
                (close_price - self.daily_open_price) / self.daily_open_price
            ) * 100

            logger.debug(
                f"📊 {self.symbol} | Precio: {close_price:.2f} | "
                f"Apertura: {self.daily_open_price:.2f} | "
                f"Cambio: {price_change_pct:.2f}%"
            )

            # Lógica de trading
            if not self.position_open:
                await self._check_entry_condition(
                    close_price, price_change_pct, current_time
                )
            else:
                await self._check_exit_condition(
                    close_price, price_change_pct, current_time
                )
                await self._notify_pnl(close_price, current_time)

        except Exception as e:
            logger.error(f"⚠️ Error procesando actualización: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _extract_close_price(self, kline_data):
        try:
            # Formato LISTA: [symbol, open_time, close_time, open, close, high, low, volume]
            if isinstance(kline_data, (list, tuple)):
                if len(kline_data) >= 5:
                    return float(kline_data[4])  # Índice 4 = close
                else:
                    logger.error(f"Lista kline incompleta (len={len(kline_data)})")
                    return None

            # Formato DICCIONARIO (fallback)
            elif isinstance(kline_data, dict):
                close_keys = ["close", "c", "closePrice", "close_price"]
                for key in close_keys:
                    if key in kline_data and kline_data[key] is not None:
                        try:
                            return float(kline_data[key])
                        except (ValueError, TypeError):
                            continue

                logger.warning(
                    f"⚠️ No se encontró precio de cierre en dict: {kline_data.keys()}"
                )
                return None

            else:
                logger.warning(f"⚠️ Formato kline no reconocido: {type(kline_data)}")
                return None

        except Exception as e:
            logger.error(f"❌ Error extrayendo precio de cierre: {e}")
            return None

    async def _check_and_update_daily_open(self, current_time: datetime):
        """
        🔧 CORREGIDO: Actualización de apertura con validaciones
        """
        try:
            current_date = current_time.date()

            # Solo actualizar si es nuevo día Y no hay posición activa
            if (
                self.last_open_check_date == current_date
                or self.position_open
                or self.daily_open_time is None
            ):
                return

            logger.info(
                f"🔄 Nuevo día detectado ({current_date}). Actualizando precio de apertura..."
            )

            response = self.rest_client.get_all_klines(
                list_symbols=[self.symbol], interval="1d", limit=1
            )

            if self.symbol not in response or len(response[self.symbol]) == 0:
                logger.error("❌ No se pudo obtener nueva apertura diaria")
                self.last_open_check_date = current_date
                return

            daily_candle = response[self.symbol][0]
            new_open_price = None
            new_open_time = None

            # Extraer usando mismo método robusto
            if isinstance(daily_candle, (list, tuple)) and len(daily_candle) >= 4:
                try:
                    new_open_price = float(daily_candle[3])  # Índice 3 = open
                    new_open_time = datetime.fromtimestamp(
                        int(daily_candle[1]) / 1000, tz=timezone.utc
                    )
                except (ValueError, TypeError, IndexError) as e:
                    logger.error(f"Error extrayendo nueva apertura: {e}")

            elif isinstance(daily_candle, dict):
                # Fallback a diccionario
                new_open_price = float(daily_candle.get("open", 0))
                timestamp = daily_candle.get("open_time") or daily_candle.get(
                    "openTime"
                )
                if timestamp:
                    new_open_time = datetime.fromtimestamp(
                        int(timestamp) / 1000, tz=timezone.utc
                    )

            # Validar y aplicar
            if new_open_price and new_open_price > 0:
                if new_open_time is None:
                    new_open_time = datetime.now(timezone.utc)

                # Solo actualizar si es del día correcto
                if new_open_time.date() == current_date:
                    old_open = self.daily_open_price
                    self.daily_open_price = new_open_price
                    self.daily_open_time = new_open_time

                    logger.info(
                        f"✅ Apertura actualizada: {old_open:.2f} → {new_open_price:.2f}"
                    )
                else:
                    logger.warning("⚠️ Apertura obtenida no corresponde al día actual")

            self.last_open_check_date = current_date

        except Exception as e:
            logger.error(f"❌ Error actualizando apertura diaria: {e}")
            self.last_open_check_date = current_time.date()

    async def _check_entry_condition(
        self, price: float, change_pct: float, current_time: datetime
    ):
        """Verificar condición de entrada."""
        if change_pct <= self.entry_threshold:
            logger.info(
                f"🎯 Condición de ENTRADA: {change_pct:.2f}% <= {self.entry_threshold}%"
            )

            position_size_usdt = self.base_capital * (
                self.position_size_percent / 100.0
            )

            await self._emit_signal(
                signal_type="BUY",
                price=price,
                reason=f"Caída del {change_pct:.2f}% desde apertura ({self.daily_open_price:.2f})",
                position_size_usdt=position_size_usdt,
                current_time=current_time,
            )

            self.position_open = True
            self.entry_price = price
            self.entry_time = current_time

            logger.info(
                f"💰 Posición abierta: {position_size_usdt:.2f} USDT @ {price:.2f}"
            )

    async def _check_exit_condition(
        self, price: float, change_pct: float, current_time: datetime
    ):
        """Verificar condición de salida."""
        if self.daily_open_price is None or self.daily_open_price <= 0:
            return

        change_from_open_pct = (
            (price - self.daily_open_price) / self.daily_open_price
        ) * 100

        if change_from_open_pct >= self.exit_threshold:
            logger.info(
                f"🎯 Condición de SALIDA: {change_from_open_pct:.2f}% >= {self.exit_threshold}%"
            )

            if self.entry_price and self.entry_price > 0:
                pnl_pct = ((price - self.entry_price) / self.entry_price) * 100
                pnl_usdt = self.base_capital * (pnl_pct / 100.0)
            else:
                pnl_pct = 0.0
                pnl_usdt = 0.0

            await self._emit_signal(
                signal_type="SELL",
                price=price,
                reason=f"Recuperación {change_from_open_pct:.2f}% desde apertura | PnL: {pnl_pct:.2f}%",
                position_size_usdt=self.base_capital + pnl_usdt,
                current_time=current_time,
            )

            self.position_open = False
            self.entry_price = None
            self.entry_time = None

            logger.info(
                f"🔒 Posición cerrada: PnL {pnl_pct:.2f}% ({pnl_usdt:.2f} USDT)"
            )

    async def _notify_pnl(self, current_price: float, current_time: datetime):
        """Notificar PnL actual."""
        if self.entry_price is None or self.entry_price <= 0:
            return

        if (
            self.last_pnl_notification is None
            or (current_time - self.last_pnl_notification).total_seconds() >= 60
        ):
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            pnl_usdt = self.base_capital * (pnl_pct / 100.0)

            change_from_open_pct = (
                (current_price - self.daily_open_price) / self.daily_open_price
            ) * 100

            logger.info(
                f"📈 PnL: {pnl_pct:.2f}% ({pnl_usdt:.2f} USDT) | "
                f"Cambio desde apertura: {change_from_open_pct:.2f}% (meta: {self.exit_threshold}%)"
            )

            self.last_pnl_notification = current_time

    async def _emit_signal(
        self,
        signal_type: str,
        price: float,
        reason: str,
        position_size_usdt: float,
        current_time: datetime,
    ):
        """Construye y emite señal validada."""

        # Validación previa
        if position_size_usdt <= 0:
            logger.error(f"❌ Tamaño de posición inválido: {position_size_usdt}")
            return

        signal_data = {
            "symbol": self.symbol,
            "type": signal_type,
            "price": price,
            "position_size_usdt": position_size_usdt,
            "timestamp": current_time.isoformat(),
            "reason": reason,
            "risk_params": self.RiskParameters(),
            "strategy_name": "BTC_Daily_Open",
        }

        validated_signal = ValidatedSignal.create_safe_signal(signal_data)

        if validated_signal is None:
            logger.error("❌ Señal inválida descartada")
            return

        # Persistir
        try:
            session = db.get_session()
            repo = SignalRepository(session)
            repo.create(
                bot_id=self.bot_id,
                strategy_name="BTC_Daily_Open",
                symbol=self.symbol,
                direction=signal_type,
                price=price,
                params_snapshot={
                    "entry_threshold": self.entry_threshold,
                    "exit_threshold": self.exit_threshold,
                    "position_size_percent": self.position_size_percent,
                    "base_capital": self.base_capital,
                    "daily_open_price": self.daily_open_price,
                    "risk_params": str(validated_signal["risk_params"]),
                },
                run_id=self.run_db_id,
                reason=reason,
                indicator_snapshot={
                    "daily_open_price": self.daily_open_price,
                    "current_price": price,
                    "change_pct": (
                        (price - self.daily_open_price) / self.daily_open_price
                    )
                    * 100,
                    "position_size_usdt": position_size_usdt,
                },
            )
            session.close()
        except Exception as e:
            logger.error(f"Error persistiendo señal: {e}")

        await self.signal_queue.put(validated_signal)
        logger.info(f"📨 Señal emitida: {signal_type} {self.symbol} @ {price:.2f}")

    class RiskParameters(BaseStrategy.RiskParameters):
        def __init__(self):
            super().__init__(
                position_size=100.0, max_risk_per_trade=100.0, max_open_positions=1
            )

    async def start(self, symbols: list[str]):
        """Inicia la estrategia."""
        self._request_for_init(symbols=[self.symbol])

        logger.info(f"🚀 Estrategia BTC_Daily_Open iniciada")
        logger.info(f"   - Apertura: {self.daily_open_price:.2f}")
        logger.info(f"   - Entrada: {self.entry_threshold}%")
        logger.info(f"   - Salida: {self.exit_threshold}%")
        logger.info(f"   - Capital: {self.base_capital} USDT")

        collector = RealTimeDataCollector(
            symbols=[self.symbol],
            on_update=self._handle_update,
            interval="1m",
        )

        await collector.start()
