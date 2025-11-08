from utils.logger import Logger
import pandas as pd
import pandas_ta as ta
import asyncio

from strategies.BaseStrategy import BaseStrategy

from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.signal_repository import SignalRepository

from contracts.signal_contract import RSISignalContract, ValidatedSignal

logger = Logger.get_logger(__name__)

class BTC_RSI_Strategy(BaseStrategy):
    """
    Estrategia basada en el RSI aplicada a múltiples símbolos en tiempo real.
    """

    def __init__(
        self, signal_queue: asyncio.Queue, bot_id: int, run_db_id: int | None = None, rsi_period=14, overbought=70, oversold=30
    ):
        """
        :param signal_queue: cola asíncrona para enviar señales
        :param bot_id: identificador del bot en BD
        :param run_db_id: identificador del BotRun en BD
        :param rsi_period: período del RSI (por defecto 14)
        :param overbought: nivel de sobrecompra (por defecto 70)
        :param oversold: nivel de sobreventa (por defecto 30)
        """
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.candles: dict[str, pd.DataFrame] = {}
        self.rest_client = BinanceRESTClient(testnet=True)

    # =====================================================
    # 🔹 CARGA INICIAL
    # =====================================================
    def _request_for_init(self, symbols: list[str]):
        """Solicita datos históricos iniciales para los símbolos."""
        response = self.rest_client.get_all_klines(
            list_symbols=symbols, interval="1m", limit=30
        )

        for symbol, data in response.items():
            df = pd.DataFrame(data)
            df["RSI"] = ta.rsi(df["close"], length=self.rsi_period)
            self.candles[symbol] = df

        logger.info(
            f"✅ Datos históricos iniciales cargados ({len(symbols)} símbolos)."
        )

    # =====================================================
    # 🔹 ACTUALIZACIÓN EN TIEMPO REAL
    # =====================================================
    async def _handle_update(self, last_candles: dict):
        """
        Actualiza los DataFrames con nuevas velas cerradas recibidas del WebSocket.
        VERSIÓN CORREGIDA - Usa contrato de señales
        """
        for symbol, kline in last_candles.items():
            try:
                open_time = int(kline[1])
                close_time = int(kline[2])
                open_p = float(kline[3])
                close_p = float(kline[4])
                high_p = float(kline[5])
                low_p = float(kline[6])
                volume = float(kline[7])

                new_row = pd.DataFrame(
                    [
                        {
                            "open_time": open_time,
                            "close_time": close_time,
                            "open": open_p,
                            "close": close_p,
                            "high": high_p,
                            "low": low_p,
                            "volume": volume,
                        }
                    ]
                )

                if symbol not in self.candles:
                    logger.warning(
                        f"⚠️ No existe DataFrame para {symbol}, se crea uno nuevo."
                    )
                    self.candles[symbol] = new_row
                else:
                    df = self.candles[symbol].iloc[1:].reset_index(drop=True)
                    df = pd.concat([df, new_row], ignore_index=True)
                    df["RSI"] = ta.rsi(df["close"], length=self.rsi_period)
                    self.candles[symbol] = df

                    rsi_value = df["RSI"].iloc[-1]
                    logger.info(
                        f"✅ {symbol} actualizado — Último cierre: {close_p:.2f} | RSI: {rsi_value:.2f}"
                    )

                    # 🚨 GENERAR SEÑAL SI HAY SOBRECOMPRA O SOBREVENTA - VERSIÓN CORREGIDA
                    if rsi_value >= self.overbought:
                        # ✅ Usar el nuevo método validado
                        await self._emit_signal(
                            symbol=symbol,
                            signal_type="SELL",
                            price=close_p,
                            rsi=float(rsi_value),
                            reason="RSI>=overbought"
                        )
                        await asyncio.sleep(0.1)

                    elif rsi_value <= self.oversold:
                        # ✅ Usar el nuevo método validado
                        await self._emit_signal(
                            symbol=symbol,
                            signal_type="BUY",
                            price=close_p,
                            rsi=float(rsi_value),
                            reason="RSI<=oversold"
                        )
                        await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"⚠️ Error procesando actualización de {symbol}: {e}")

    async def _emit_signal(self, symbol: str, signal_type: str, price: float, rsi: float, reason: str):
        """NUEVO MÉTODO: Emite señales validadas según contrato"""

        # 🔥 VALIDACIÓN PREVIA
        if rsi is None:
            logger.error(f"❌ No se puede emitir señal: RSI es None para {symbol}")
            return

        if not isinstance(rsi, (int, float)):
            logger.error(f"❌ RSI inválido para {symbol}: {rsi} (tipo: {type(rsi)})")
            return

        signal_data = {
            "symbol": symbol,
            "type": signal_type,
            "price": price,
            "rsi": float(rsi),  # ✅ Conversión segura
            "reason": reason,
            "risk_params": self.RiskParameters(),
            "strategy_name": "BTC_RSI"
        }

        # 🔥 VALIDAR Y NORMALIZAR LA SEÑAL
        validated_signal = ValidatedSignal.create_safe_signal(signal_data)

        if validated_signal is None:
            logger.error(f"❌ Señal inválida descartada para {symbol}")
            return

        # Persistir la señal
        try:
            session = db.get_session()
            repo = SignalRepository(session)
            repo.create(
                bot_id=self.bot_id,
                strategy_name="BTC_RSI",
                symbol=symbol,
                direction=signal_type,
                price=price,
                params_snapshot={
                    "rsi_period": self.rsi_period,
                    "overbought": self.overbought,
                    "oversold": self.oversold,
                    "risk_params": getattr(validated_signal["risk_params"], "__dict__",
                                           str(validated_signal["risk_params"]))
                },
                run_id=self.run_db_id,
                reason=reason,
                indicator_snapshot={"RSI": float(rsi), "close": price},
            )
            session.close()
        except Exception as e:
            logger.error(f"Error persistiendo señal {signal_type}: {e}")
            return  # ✅ No emitir señal si falla la persistencia

        # 🔥 ENVIAR SEÑAL VALIDADA
        await self.signal_queue.put(validated_signal)
        logger.info(f"📨 Señal BTC_RSI validada: {signal_type} {symbol} @ {price:.2f} — {reason}")

    class RiskParameters(BaseStrategy.RiskParameters):
        def __init__(self):
            super().__init__(max_drawdown=0.5, position_size=0.01, max_open_positions=5)

    # =====================================================
    # 🔹 INICIO DE LA ESTRATEGIA
    # =====================================================
    async def start(self, symbols: list[str]):
        """Inicia la estrategia con datos históricos y actualizaciones en tiempo real."""
        self._request_for_init(symbols=symbols)

        for symbol, df in self.candles.items():
            logger.info(f"Ultimas 3 velas de {symbol}:\n{df.tail(3)}")

        collector = RealTimeDataCollector(
            symbols=symbols,
            on_update=self._handle_update,
            interval="1m",
        )

        logger.info("Estrategia RSI iniciada. Esperando nuevas velas...")
        await collector.start()
