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

logger = Logger.get_logger(__name__)


class BTC_Daily_Open_Strategy(BaseStrategy):
    """
    Estrategia basada en el precio de apertura diario de Bitcoin.

    Reglas MODIFICADAS:
    1. Tomar el precio de apertura de la primera vela M1 del día (00:00 UTC)
    2. Si el precio actual cae -1% desde la apertura, COMPRAR con 100% del capital (10 USDT)
    3. Notificar PnL en cada nueva vela
    4. Cerrar posición cuando el precio suba +2% desde la APERTURA (no desde la entrada)
    5. Mantener la posición abierta hasta que se cumpla la condición de salida,
       independientemente del cambio de día
    """

    def __init__(
            self,
            signal_queue: asyncio.Queue,
            bot_id: int,
            run_db_id: int | None = None,
            entry_threshold: float = -1.0,  # -1%
            exit_threshold: float = 2.0,    # +2%
            position_size_percent: float = 100.0,  # 100% del capital
            base_capital: float = 10.0,  # 10 USDT
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
        self.position_open = False
        self.entry_price = None
        self.entry_time = None
        self.current_price = None
        self.last_pnl_notification = None

        self.rest_client = BinanceRESTClient(testnet=True)

    def _request_for_init(self, symbols: list[str]):
        """Solicita datos históricos para determinar el precio de apertura del día actual."""
        try:
            # Obtener velas diarias para encontrar la apertura del día actual
            response = self.rest_client.get_all_klines(
                list_symbols=[self.symbol],
                interval="1d",
                limit=2  # Solo necesitamos el día actual y posiblemente el anterior
            )

            if self.symbol in response and len(response[self.symbol]) > 0:
                # La última vela diaria es el día actual
                daily_data = response[self.symbol][-1]
                self.daily_open_price = float(daily_data[1])  # Precio de apertura

                logger.info(f"✅ Precio de apertura diario cargado: {self.daily_open_price:.2f} "
                            f"para {datetime.utcnow().strftime('%Y-%m-%d')}")

                # Verificar si ya estamos en posición (por si el bot se reinicia)
                self._check_existing_position()

            else:
                logger.error("❌ No se pudieron obtener datos diarios para BTC")

        except Exception as e:
            logger.error(f"❌ Error cargando precio de apertura diario: {e}")

    def _check_existing_position(self):
        """Verificar si ya existe una posición abierta (para casos de reinicio)."""
        # Esta implementación dependerá de tu sistema de tracking de posiciones
        # Por ahora, asumimos que no hay posición al iniciar
        self.position_open = False
        self.entry_price = None
        self.entry_time = None

    async def _handle_update(self, last_candles: dict):
        """Procesa cada nueva vela M1 recibida del WebSocket."""
        if self.symbol not in last_candles:
            return

        try:
            kline = last_candles[self.symbol]
            close_time = int(kline[2])
            close_p = float(kline[4])
            self.current_price = close_p

            current_time = datetime.utcnow()

            # Verificar si es un nuevo día (00:00 UTC)
            self._check_new_day(current_time)

            # Si no tenemos precio de apertura, usar el precio actual como referencia temporal
            if self.daily_open_price is None:
                self.daily_open_price = close_p
                logger.info(f"🔄 Usando precio actual como referencia temporal: {close_p:.2f}")

            # Calcular cambio porcentual desde la apertura
            price_change_pct = ((close_p - self.daily_open_price) / self.daily_open_price) * 100

            logger.debug(f"📊 {self.symbol} | Precio: {close_p:.2f} | "
                         f"Apertura: {self.daily_open_price:.2f} | "
                         f"Cambio: {price_change_pct:.2f}%")

            # Lógica de trading
            if not self.position_open:
                await self._check_entry_condition(close_p, price_change_pct, current_time)
            else:
                await self._check_exit_condition(close_p, price_change_pct, current_time)
                await self._notify_pnl(close_p, current_time)

        except Exception as e:
            logger.error(f"⚠️ Error procesando actualización de {self.symbol}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _check_new_day(self, current_time: datetime):
        """Verificar si es un nuevo día y actualizar el precio de apertura."""
        # Para Bitcoin, el día comienza a las 00:00 UTC
        if current_time.hour == 0 and current_time.minute == 0:
            # Es la primera vela del nuevo día, usar este precio como nueva apertura
            # PERO solo si no tenemos posición abierta
            if not self.position_open and self.current_price is not None:
                new_open_price = self.current_price
                if new_open_price != self.daily_open_price:
                    self.daily_open_price = new_open_price
                    logger.info(f"🔄 Nuevo día - Precio de apertura actualizado: {new_open_price:.2f}")

    async def _check_entry_condition(self, price: float, change_pct: float, current_time: datetime):
        """Verificar condición de entrada."""
        if change_pct <= self.entry_threshold:
            logger.info(f"🎯 Condición de ENTRADA detectada: {change_pct:.2f}% <= {self.entry_threshold}%")

            # Calcular tamaño de posición
            position_size_usdt = self.base_capital * (self.position_size_percent / 100.0)

            await self._emit_signal(
                signal_type="BUY",
                price=price,
                reason=f"Caída del {change_pct:.2f}% desde apertura diaria",
                position_size_usdt=position_size_usdt,
                current_time=current_time
            )

            # Actualizar estado
            self.position_open = True
            self.entry_price = price
            self.entry_time = current_time

            logger.info(f"💰 Posición abierta: {position_size_usdt:.2f} USDT @ {price:.2f}")

    async def _check_exit_condition(self, price: float, change_pct: float, current_time: datetime):
        """Verificar condición de salida BASADA EN PRECIO DE APERTURA (MODIFICADO)."""
        if self.daily_open_price is None:
            return

        # Calcular cambio desde el precio de apertura (NO desde entrada)
        change_from_open_pct = ((price - self.daily_open_price) / self.daily_open_price) * 100

        if change_from_open_pct >= self.exit_threshold:
            logger.info(
                f"🎯 Condición de SALIDA detectada: {change_from_open_pct:.2f}% >= {self.exit_threshold}% desde APERTURA")

            # Calcular PnL real desde entrada
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
                position_size_usdt=self.base_capital + pnl_usdt,  # Capital + ganancias
                current_time=current_time
            )

            # Resetear estado
            self.position_open = False
            self.entry_price = None
            self.entry_time = None

            logger.info(f"🔒 Posición cerrada: PnL desde entrada {pnl_pct_from_entry:.2f}% ({pnl_usdt:.2f} USDT)")

    async def _notify_pnl(self, current_price: float, current_time: datetime):
        """Notificar PnL actual desde la entrada."""
        if self.entry_price is None:
            return

        # Notificar máximo una vez por minuto
        if (self.last_pnl_notification is None or
                (current_time - self.last_pnl_notification).total_seconds() >= 60):
            # PnL desde entrada
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            pnl_usdt = self.base_capital * (pnl_pct / 100.0)

            # Cambio desde apertura (ahora más importante)
            change_from_open_pct = ((current_price - self.daily_open_price) / self.daily_open_price) * 100

            logger.info(f"📈 PnL Desde Entrada: {pnl_pct:.2f}% ({pnl_usdt:.2f} USDT) | "
                        f"Cambio desde apertura: {change_from_open_pct:.2f}% (Objetivo: {self.exit_threshold}%)")

            self.last_pnl_notification = current_time

    async def _emit_signal(self, signal_type: str, price: float, reason: str,
                           position_size_usdt: float, current_time: datetime):
        """Construye, persiste y emite una señal."""
        signal = {
            "symbol": self.symbol,
            "type": signal_type,
            "price": price,
            "position_size_usdt": position_size_usdt,
            "risk_params": self.RiskParameters(),
            "timestamp": current_time.isoformat()
        }

        # Persistir la señal
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
                    "entry_price": self.entry_price,
                    "risk_params": getattr(signal["risk_params"], "__dict__", str(signal["risk_params"]))
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

        await self.signal_queue.put(signal)
        logger.info(f"Señal BTC_Daily_Open: {signal_type} {self.symbol} @ {price:.2f} — {reason}")

    class RiskParameters(BaseStrategy.RiskParameters):
        def __init__(self):
            super().__init__(
                position_size=100.0,  # 100% del capital
                max_risk_per_trade=100.0,  # 100% del equity
                stop_loss_pct=-1.0,  # No usar stop-loss tradicional
                take_profit_pct=2.0,  # TP en +2% desde APERTURA
                max_drawdown=10.0,  # Drawdown máximo permitido
                max_daily_loss=100.0,  # Pérdida máxima diaria
                max_total_loss=100.0  # Pérdida total máxima
            )

    async def start(self, symbols: list[str]):
        """Inicia la estrategia con datos históricos y actualizaciones en tiempo real."""
        self._request_for_init(symbols=[self.symbol])

        logger.info(f"🚀 Estrategia BTC_Daily_Open iniciada")
        logger.info(f"   - Símbolo: {self.symbol}")
        logger.info(f"   - Precio apertura: {self.daily_open_price or 'No disponible'}")
        logger.info(f"   - Entrada: {self.entry_threshold}% desde apertura")
        logger.info(f"   - Salida: +{self.exit_threshold}% desde APERTURA (MODIFICADO)")
        logger.info(f"   - Capital: {self.base_capital} USDT ({self.position_size_percent}% por operación)")

        collector = RealTimeDataCollector(
            symbols=[self.symbol],
            on_update=self._handle_update,
            interval="1m",
        )

        logger.info("Esperando nuevas velas M1...")
        await collector.start()