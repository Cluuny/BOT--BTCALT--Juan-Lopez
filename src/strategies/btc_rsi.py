import logging
import pandas as pd
import pandas_ta as ta

from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class BTC_RSI_Strategy:
    """
    Estrategia basada en el RSI aplicada a múltiples símbolos en tiempo real.
    """

    def __init__(self, rsi_period=14, overbought=70, oversold=30):
        """
        :param rsi_period: período del RSI (por defecto 14)
        :param overbought: nivel de sobrecompra (por defecto 70)
        :param oversold: nivel de sobreventa (por defecto 30)
        """
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.candles: dict[str, pd.DataFrame] = {}
        self.rest_client = BinanceRESTClient()

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

        logging.info(
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
                    logging.warning(
                        f"⚠️ No existe DataFrame para {symbol}, se crea uno nuevo."
                    )
                    self.candles[symbol] = new_row
                else:
                    # Eliminar la vela más antigua y agregar la nueva
                    df = self.candles[symbol].iloc[1:].reset_index(drop=True)
                    df = pd.concat([df, new_row], ignore_index=True)

                    # Recalcular el RSI
                    df["RSI"] = ta.rsi(df["close"], length=self.rsi_period)

                    self.candles[symbol] = df
                    logging.info(
                        f"✅ {symbol} actualizado — Último cierre: {close_p:.2f} | RSI: {df['RSI'].iloc[-1]:.2f}"
                    )

            except Exception as e:
                logging.error(f"⚠️ Error procesando actualización de {symbol}: {e}")

    # =====================================================
    # 🔹 INICIO DE LA ESTRATEGIA
    # =====================================================
    async def start(self, symbols: list[str]):
        """Inicia la estrategia con datos históricos y actualizaciones en tiempo real."""

        # Cargar velas históricas y calcular indicadores
        self._request_for_init(symbols=symbols)

        # Mostrar últimos registros de cada símbolo
        for symbol, df in self.candles.items():
            logging.info(f"ULTIMAS 3 VELAS DE {symbol}:\n{df.tail(3)}")

        # Inicio del recolector
        collector = RealTimeDataCollector(
            symbols=symbols,
            on_update=self._handle_update,  # callback directo
            interval="1m",
        )

        logging.info("Estrategia RSI iniciada. Esperando nuevas velas...")
        await collector.start()
