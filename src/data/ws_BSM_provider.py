import asyncio
import logging
from binance import AsyncClient, BinanceSocketManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class RealTimeDataCollector:
    """
    Cliente WebSocket basado en BinanceSocketManager para recibir datos
    de velas (kline) en tiempo real, por defecto intervalos de 1m.
    """

    def __init__(self, symbols, on_update=None, interval="1m", reconnect_delay=5):
        """
        :param symbols: lista de símbolos, e.g. ["BTCUSDT", "ETHUSDT"]
        :param on_update: callback async -> async def on_update(matrix)
        :param interval: intervalo de velas (por defecto "1m")
        :param reconnect_delay: segundos para reintento de conexión
        """
        self.symbols = [s.lower() for s in symbols]
        self.interval = interval
        self.reconnect_delay = reconnect_delay
        self.on_update = on_update

        self.keep_running = True
        self.client = None
        self.bsm = None

    async def start(self):
        """Inicia la conexión y recibe los datos en tiempo real (sin duplicados)."""
        socket = None

        while self.keep_running:
            try:
                if not self.client:
                    self.client = await AsyncClient.create()
                    self.bsm = BinanceSocketManager(self.client, user_timeout=60)
                    logging.info("✅ Conectado a Binance WebSocket")

                if not socket:
                    streams = [f"{s}@kline_{self.interval}" for s in self.symbols]
                    logging.info(f"🔗 Iniciando stream con: {streams}")
                    socket = self.bsm.multiplex_socket(streams)

                # Conexión abierta por while
                async with socket as s:
                    while self.keep_running:
                        try:
                            msg = await s.recv()
                            await self._process_message(msg)
                        except asyncio.TimeoutError:
                            logging.warning(
                                "⌛ Timeout, esperando siguiente mensaje..."
                            )
                            continue
                        except Exception as e:
                            logging.error(f"⚠️ Error recibiendo datos: {e}")
                            break

            except Exception as e:
                logging.error(f"⚠️ Error general del WebSocket: {e}")
                await asyncio.sleep(self.reconnect_delay)

                # Cerrar y reiniciar conexión completa
                if self.client:
                    await self.client.close_connection()
                    self.client = None
                    self.bsm = None
                    socket = None
                    logging.info("🔌 Cliente Binance cerrado correctamente.")

    async def _process_message(self, msg):
        """Procesa cada mensaje kline y envía solo la última vela cerrada del símbolo."""
        data = msg.get("data", msg)
        if data.get("e") != "kline":
            return

        k = data["k"]
        symbol = data["s"]

        # Solo procesar velas cerradas
        if not k["x"]:
            return

        # Generar ID único de la vela
        kline_id = (symbol, k["t"], k["T"])

        # Evitar procesar la misma vela más de una vez
        if not hasattr(self, "last_processed"):
            self.last_processed = {}
        if self.last_processed.get(symbol) == kline_id:
            return
        self.last_processed[symbol] = kline_id

        # Extraer datos relevantes
        kline_entry = [
            symbol,
            int(k["t"]),
            int(k["T"]),
            float(k["o"]),
            float(k["c"]),
            float(k["h"]),
            float(k["l"]),
            float(k["v"]),
        ]

        # Reiniciar el diccionario para enviar solo un símbolo por actualización
        self.last_candles = {symbol: kline_entry}

        # Enviar al callback
        if self.on_update:
            await self.on_update(self.last_candles)

    async def stop(self):
        """Detiene la recolección de datos."""
        self.keep_running = False
        if self.client:
            await self.client.close_connection()
        logging.info("🛑 Recolección de datos detenida.")
