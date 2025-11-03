from utils.logger import Logger
import pandas as pd
import pandas_ta as ta
import asyncio

from strategies.BaseStrategy import BaseStrategy

from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.signal_repository import SignalRepository

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

                    # 🚨 GENERAR SEÑAL SI HAY SOBRECOMPRA O SOBREVENTA
                    if rsi_value >= self.overbought:
                        signal = {
                            "symbol": symbol,
                            "type": "SELL",
                            "rsi": float(rsi_value),  # Convertir a float nativo
                            "price": close_p,
                            "risk_params": self.RiskParameters(),
                        }
                        # Persistir la señal
                        try:
                            session = db.get_session()
                            repo = SignalRepository(session)
                            repo.create(
                                bot_id=self.bot_id,
                                strategy_name="BTC_RSI",
                                symbol=symbol,
                                direction="SELL",
                                price=close_p,
                                params_snapshot={
                                    "rsi_period": self.rsi_period,
                                    "overbought": self.overbought,
                                    "oversold": self.oversold,
                                    "risk_params": getattr(signal["risk_params"], "__dict__", str(signal["risk_params"]))
                                },
                                run_id=self.run_db_id,
                                reason="RSI>=overbought",
                                indicator_snapshot={"RSI": float(rsi_value), "close": close_p},
                            )
                            session.close()
                        except Exception as e:
                            logger.error(f"Error persistiendo señal SELL: {e}")
                        await self.signal_queue.put(signal)
                        logger.info(f"📉 Señal RSI generada: {signal}")
                        await asyncio.sleep(0.1)  # Pequeño delay entre señales

                    elif rsi_value <= self.oversold:
                        signal = {
                            "symbol": symbol,
                            "type": "BUY",
                            "rsi": float(rsi_value),  # Convertir a float nativo
                            "price": close_p,
                            "risk_params": self.RiskParameters(),
                        }
                        # Persistir la señal
                        try:
                            session = db.get_session()
                            repo = SignalRepository(session)
                            repo.create(
                                bot_id=self.bot_id,
                                strategy_name="BTC_RSI",
                                symbol=symbol,
                                direction="BUY",
                                price=close_p,
                                params_snapshot={
                                    "rsi_period": self.rsi_period,
                                    "overbought": self.overbought,
                                    "oversold": self.oversold,
                                    "risk_params": getattr(signal["risk_params"], "__dict__", str(signal["risk_params"]))
                                },
                                run_id=self.run_db_id,
                                reason="RSI<=oversold",
                                indicator_snapshot={"RSI": float(rsi_value), "close": close_p},
                            )
                            session.close()
                        except Exception as e:
                            logger.error(f"Error persistiendo señal BUY: {e}")
                        await self.signal_queue.put(signal)
                        logger.info(f"📈 Señal RSI generada: {signal}")
                        await asyncio.sleep(0.1)  # Pequeño delay entre señales

            except Exception as e:
                logger.error(f"⚠️ Error procesando actualización de {symbol}: {e}")

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
