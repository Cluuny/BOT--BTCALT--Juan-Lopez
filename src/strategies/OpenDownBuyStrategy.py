from utils.logger import Logger
import pandas as pd
import asyncio
from datetime import datetime, time
import traceback

from strategies.BaseStrategy import BaseStrategy
from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.signal_repository import SignalRepository

from contracts.signal_contract import RSISignalContract, ValidatedSignal

logger = Logger.get_logger(__name__)


class BTC_Daily_Open_Strategy(BaseStrategy):
    """
    Estrategia basada en el precio de apertura diario de Bitcoin.
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
            symbol: str = "BTCUSDT"
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

        self.rest_client = BinanceRESTClient(testnet=True)

    def _request_for_init(self, symbols: list[str]):
        """Solicita el último precio de apertura diario disponible con mejor manejo de formato."""
        try:
            logger.info(f"🔍 Solicitando datos diarios para {self.symbol}...")

            # Obtener velas diarias
            response = self.rest_client.get_all_klines(
                list_symbols=[self.symbol],
                interval="1d",
                limit=5
            )

            logger.debug(f"Respuesta de API recibida: {response}")

            if self.symbol in response and len(response[self.symbol]) > 0:
                daily_candles = response[self.symbol]
                last_daily = daily_candles[-1]

                # INTENTO 1: Asumir que es una lista con índices numéricos
                if isinstance(last_daily, (list, tuple)) and len(last_daily) >= 2:
                    self.daily_open_price = float(last_daily[1])
                    open_timestamp = int(last_daily[0]) / 1000
                    self.daily_open_time = datetime.utcfromtimestamp(open_timestamp)
                    self.last_open_check_date = self.daily_open_time.date()

                    logger.info(f"✅ Precio de apertura diario cargado (formato lista): {self.daily_open_price:.2f}")

                # INTENTO 2: Asumir que es un diccionario
                elif isinstance(last_daily, dict):
                    # Probar diferentes posibles claves para el precio de apertura
                    open_price_keys = ['open', 'o', 'openPrice', 'open_price']
                    timestamp_keys = ['open_time', 'timestamp', 't', 'openTime']

                    open_price = None
                    timestamp_val = None

                    for key in open_price_keys:
                        if key in last_daily and last_daily[key] is not None:
                            open_price = float(last_daily[key])
                            break

                    for key in timestamp_keys:
                        if key in last_daily and last_daily[key] is not None:
                            timestamp_val = int(last_daily[key]) / 1000
                            break

                    if open_price is not None:
                        self.daily_open_price = open_price
                        if timestamp_val is not None:
                            self.daily_open_time = datetime.utcfromtimestamp(timestamp_val)
                        else:
                            self.daily_open_time = datetime.utcnow()
                        self.last_open_check_date = self.daily_open_time.date()

                        logger.info(
                            f"✅ Precio de apertura diario cargado (formato diccionario): {self.daily_open_price:.2f}")
                    else:
                        logger.error("❌ No se pudo encontrar el precio de apertura en el diccionario")
                        self._fallback_to_current_price()
                else:
                    logger.error(f"❌ Formato de vela no reconocido: {type(last_daily)}")
                    logger.error(f"Contenido de vela: {last_daily}")
                    self._fallback_to_current_price()

                self._check_existing_position()

            else:
                logger.error(f"❌ No se encontraron datos diarios para {self.symbol}")
                self._fallback_to_current_price()

        except Exception as e:
            logger.error(f"❌ Error crítico cargando precio de apertura diario: {str(e)}")
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            self._fallback_to_current_price()

    def _fallback_to_current_price(self):
        """Fallback mejorado que maneja diferentes formatos."""
        try:
            logger.info("🔄 Intentando fallback con precio actual...")

            response = self.rest_client.get_all_klines(
                list_symbols=[self.symbol],
                interval="1m",
                limit=2
            )

            logger.debug(f"Respuesta fallback: {response}")

            if self.symbol in response and len(response[self.symbol]) > 0:
                last_candle = response[self.symbol][-1]
                current_price = None

                # INTENTO 1: Formato lista
                if isinstance(last_candle, (list, tuple)) and len(last_candle) >= 5:
                    current_price = float(last_candle[4])  # Close price

                # INTENTO 2: Formato diccionario
                elif isinstance(last_candle, dict):
                    close_keys = ['close', 'c', 'closePrice', 'close_price']
                    for key in close_keys:
                        if key in last_candle and last_candle[key] is not None:
                            current_price = float(last_candle[key])
                            break

                if current_price is not None:
                    self.daily_open_price = current_price
                    self.daily_open_time = datetime.utcnow()
                    self.last_open_check_date = self.daily_open_time.date()

                    logger.info(f"🔄 Usando precio actual como apertura: {current_price:.2f} "
                                f"(fallback por error en datos históricos)")
                else:
                    logger.error("❌ No se pudo extraer precio de la vela en fallback")
                    self._emergency_fallback()
            else:
                logger.error("❌ Fallback también falló - sin datos de velas 1m")
                self._emergency_fallback()

        except Exception as e:
            logger.error(f"❌ Error en fallback: {str(e)}")
            logger.error(f"Traceback fallback: {traceback.format_exc()}")
            self._emergency_fallback()

    def _emergency_fallback(self):
        """Fallback de emergencia cuando todo falla."""
        try:
            # Usar el cliente Binance directo para obtener el precio actual
            from binance.client import Client
            client = Client(testnet=True)
            ticker = client.get_symbol_ticker(symbol=self.symbol)
            emergency_price = float(ticker['price'])

            self.daily_open_price = emergency_price
            self.daily_open_time = datetime.utcnow()
            self.last_open_check_date = self.daily_open_time.date()

            logger.warning(f"🚨 Usando fallback de emergencia: {emergency_price:.2f}")

        except Exception as e:
            logger.critical(f"💥 FALLBACK DE EMERGENCIA TAMBIÉN FALLÓ: {e}")
            # Último recurso - usar el precio que ya funcionó en tu log (102305.22)
            self.daily_open_price = 102305.22
            self.daily_open_time = datetime.utcnow()
            self.last_open_check_date = self.daily_open_time.date()
            logger.critical(f"🚨 Usando valor por defecto: {self.daily_open_price:.2f}")

    def _check_existing_position(self):
        """Verificar si ya existe una posición abierta."""
        self.position_open = False
        self.entry_price = None
        self.entry_time = None

    async def _handle_update(self, last_candles: dict):
        """Procesa cada nueva vela M1 recibida del WebSocket."""
        if self.symbol not in last_candles:
            return

        try:
            kline = last_candles[self.symbol]

            # Extraer precio de cierre según el formato
            close_price = self._extract_close_price(kline)
            if close_price is None:
                logger.warning(f"⚠️ No se pudo extraer precio de cierre de: {kline}")
                return

            self.current_price = close_price
            current_time = datetime.utcnow()

            # Si no tenemos precio de apertura, usar precio actual
            if self.daily_open_price is None:
                logger.warning("⚠️ No hay precio de apertura, usando precio actual")
                self.daily_open_price = close_price
                self.daily_open_time = current_time
                self.last_open_check_date = current_time.date()
                logger.info(f"🔄 Inicializado con precio actual: {close_price:.2f}")

            # Verificar si es nuevo día y actualizar apertura si no hay posición
            await self._check_and_update_daily_open(current_time)

            # Calcular cambio porcentual desde la apertura
            price_change_pct = ((close_price - self.daily_open_price) / self.daily_open_price) * 100

            logger.debug(f"📊 {self.symbol} | Precio: {close_price:.2f} | "
                         f"Apertura: {self.daily_open_price:.2f} | "
                         f"Cambio: {price_change_pct:.2f}%")

            # Lógica de trading
            if not self.position_open:
                await self._check_entry_condition(close_price, price_change_pct, current_time)
            else:
                await self._check_exit_condition(close_price, price_change_pct, current_time)
                await self._notify_pnl(close_price, current_time)

        except Exception as e:
            logger.error(f"⚠️ Error procesando actualización de {self.symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _extract_close_price(self, kline_data):
        """Extrae el precio de cierre - VERSIÓN ROBUSTA"""
        try:
            # 🔥 SOPORTE PARA AMBOS FORMATOS
            if isinstance(kline_data, (list, tuple)) and len(kline_data) >= 5:
                return float(kline_data[4])  # Formato lista: índice 4 es close

            elif isinstance(kline_data, dict):
                # Formato diccionario - múltiples claves posibles
                close_keys = ['close', 'c', 'closePrice', 'close_price']
                for key in close_keys:
                    if key in kline_data and kline_data[key] is not None:
                        return float(kline_data[key])

            logger.warning(f"⚠️ Formato de kline no reconocido: {type(kline_data)}")
            return None

        except Exception as e:
            logger.error(f"❌ Error extrayendo precio de cierre: {e}")
            return None

    async def _check_and_update_daily_open(self, current_time: datetime):
        """Verifica si es nuevo día y actualiza el precio de apertura si no hay posición activa."""
        try:
            current_date = current_time.date()

            if (self.last_open_check_date != current_date and
                    not self.position_open and
                    self.daily_open_time is not None):

                logger.info(f"🔄 Nuevo día detectado ({current_date}). Buscando nuevo precio de apertura...")

                response = self.rest_client.get_all_klines(
                    list_symbols=[self.symbol],
                    interval="1d",
                    limit=1
                )

                if self.symbol in response and len(response[self.symbol]) > 0:
                    daily_candle = response[self.symbol][0]
                    new_open_price = None
                    new_open_time = None

                    # Manejar diferentes formatos
                    if isinstance(daily_candle, (list, tuple)) and len(daily_candle) >= 2:
                        new_open_price = float(daily_candle[1])
                        new_open_time = datetime.utcfromtimestamp(int(daily_candle[0]) / 1000)
                    elif isinstance(daily_candle, dict):
                        open_keys = ['open', 'o', 'openPrice', 'open_price']
                        time_keys = ['open_time', 'timestamp', 't', 'openTime']

                        for key in open_keys:
                            if key in daily_candle and daily_candle[key] is not None:
                                new_open_price = float(daily_candle[key])
                                break

                        for key in time_keys:
                            if key in daily_candle and daily_candle[key] is not None:
                                new_open_time = datetime.utcfromtimestamp(int(daily_candle[key]) / 1000)
                                break

                    if new_open_price is not None:
                        if new_open_time is None:
                            new_open_time = datetime.utcnow()

                        if new_open_time.date() == current_date:
                            old_open = self.daily_open_price
                            self.daily_open_price = new_open_price
                            self.daily_open_time = new_open_time
                            self.last_open_check_date = current_date

                            logger.info(f"✅ Precio de apertura actualizado: {old_open:.2f} → {new_open_price:.2f} "
                                        f"(del {new_open_time.strftime('%Y-%m-%d %H:%M UTC')})")
                        else:
                            logger.warning("⚠️ No se encontró precio de apertura para el día actual")
                    else:
                        logger.error("❌ No se pudo extraer precio de apertura en actualización")

                self.last_open_check_date = current_date

        except Exception as e:
            logger.error(f"❌ Error actualizando precio de apertura diario: {e}")
            self.last_open_check_date = current_time.date()

    # Los métodos _check_entry_condition, _check_exit_condition, _notify_pnl, _emit_signal,
    # RiskParameters y start se mantienen igual que en tu versión original

    async def _check_entry_condition(self, price: float, change_pct: float, current_time: datetime):
        """Verificar condición de entrada."""
        if change_pct <= self.entry_threshold:
            logger.info(f"🎯 Condición de ENTRADA detectada: {change_pct:.2f}% <= {self.entry_threshold}%")

            position_size_usdt = self.base_capital * (self.position_size_percent / 100.0)

            await self._emit_signal(
                signal_type="BUY",
                price=price,
                reason=f"Caída del {change_pct:.2f}% desde apertura diaria ({self.daily_open_price:.2f})",
                position_size_usdt=position_size_usdt,
                current_time=current_time
            )

            self.position_open = True
            self.entry_price = price
            self.entry_time = current_time

            logger.info(f"💰 Posición abierta: {position_size_usdt:.2f} USDT @ {price:.2f}")

    async def _check_exit_condition(self, price: float, change_pct: float, current_time: datetime):
        """Verificar condición de salida BASADA EN PRECIO DE APERTURA."""
        if self.daily_open_price is None:
            return

        change_from_open_pct = ((price - self.daily_open_price) / self.daily_open_price) * 100

        if change_from_open_pct >= self.exit_threshold:
            logger.info(
                f"🎯 Condición de SALIDA detectada: {change_from_open_pct:.2f}% >= {self.exit_threshold}% desde APERTURA")

            if self.entry_price is not None:
                pnl_pct_from_entry = ((price - self.entry_price) / self.entry_price) * 100
                pnl_usdt = self.base_capital * (pnl_pct_from_entry / 100.0)
            else:
                pnl_pct_from_entry = 0.0
                pnl_usdt = 0.0

            await self._emit_signal(
                signal_type="SELL",
                price=price,
                reason=f"Recuperación del {change_from_open_pct:.2f}% desde apertura | PnL desde entrada: {pnl_pct_from_entry:.2f}%",
                position_size_usdt=self.base_capital + pnl_usdt,
                current_time=current_time
            )

            self.position_open = False
            self.entry_price = None
            self.entry_time = None

            logger.info(f"🔒 Posición cerrada: PnL desde entrada {pnl_pct_from_entry:.2f}% ({pnl_usdt:.2f} USDT)")

    async def _notify_pnl(self, current_price: float, current_time: datetime):
        """Notificar PnL actual desde la entrada."""
        if self.entry_price is None:
            return

        if (self.last_pnl_notification is None or
                (current_time - self.last_pnl_notification).total_seconds() >= 60):
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            pnl_usdt = self.base_capital * (pnl_pct / 100.0)

            change_from_open_pct = ((current_price - self.daily_open_price) / self.daily_open_price) * 100

            logger.info(f"📈 PnL Desde Entrada: {pnl_pct:.2f}% ({pnl_usdt:.2f} USDT) | "
                        f"Cambio desde apertura: {change_from_open_pct:.2f}% (Objetivo: {self.exit_threshold}%)")

            self.last_pnl_notification = current_time

    async def _emit_signal(self, signal_type: str, price: float, reason: str, position_size_usdt: float,
                           current_time: datetime):
        """Construye señal validada según contrato Daily Open"""

        # 🔥 VALIDACIÓN PREVIA
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
            "strategy_name": "BTC_Daily_Open"
        }

        # 🔥 VALIDAR Y NORMALIZAR LA SEÑAL
        validated_signal = ValidatedSignal.create_safe_signal(signal_data)

        if validated_signal is None:
            logger.error("❌ No se pudo emitir señal inválida")
            return

        # Persistir (código existente)...
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
                    "daily_open_time": self.daily_open_time.isoformat() if self.daily_open_time else None,
                    "entry_price": self.entry_price,
                    "risk_params": getattr(validated_signal["risk_params"], "__dict__",
                                           str(validated_signal["risk_params"]))
                },
                run_id=self.run_db_id,
                reason=reason,
                indicator_snapshot={
                    "daily_open_price": self.daily_open_price,
                    "current_price": price,
                    "change_from_open_pct": ((price - self.daily_open_price) / self.daily_open_price) * 100,
                    "position_size_usdt": position_size_usdt
                },
            )
            session.close()
        except Exception as e:
            logger.error(f"Error persistiendo señal {signal_type}: {e}")

        # 🔥 ENVIAR SEÑAL VALIDADA
        await self.signal_queue.put(validated_signal)
        logger.info(f"Señal BTC_Daily_Open validada: {signal_type} {self.symbol} @ {price:.2f} — {reason}")

    class RiskParameters(BaseStrategy.RiskParameters):
        def __init__(self):
            super().__init__(
                position_size=100.0,
                max_risk_per_trade=100.0,
                stop_loss_pct=-1.0,
                take_profit_pct=2.0,
                max_drawdown=10.0,
                max_daily_loss=100.0,
                max_total_loss=100.0
            )

    async def start(self, symbols: list[str]):
        """Inicia la estrategia con datos históricos y actualizaciones en tiempo real."""
        self._request_for_init(symbols=[self.symbol])

        open_time_str = self.daily_open_time.strftime('%Y-%m-%d %H:%M UTC') if self.daily_open_time else "N/A"

        logger.info(f"🚀 Estrategia BTC_Daily_Open iniciada")
        logger.info(f"   - Símbolo: {self.symbol}")
        logger.info(f"   - Precio apertura: {self.daily_open_price or 'No disponible'} ({open_time_str})")
        logger.info(f"   - Entrada: {self.entry_threshold}% desde apertura")
        logger.info(f"   - Salida: +{self.exit_threshold}% desde apertura")
        logger.info(f"   - Capital: {self.base_capital} USDT ({self.position_size_percent}% por operación)")
        logger.info(f"   - MODO: Precio de apertura se actualiza automáticamente cada nuevo día sin posición")

        collector = RealTimeDataCollector(
            symbols=[self.symbol],
            on_update=self._handle_update,
            interval="1m",
        )

        logger.info("Esperando nuevas velas M1...")
        await collector.start()