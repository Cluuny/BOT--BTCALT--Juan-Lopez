import asyncio
from utils.logger import Logger
from binance import AsyncClient, BinanceSocketManager

logger = Logger.get_logger(__name__)


class RealTimeDataCollector:
    """
    🔧 VERSIÓN CORREGIDA: Cliente WebSocket con race condition solucionado
    - Inicialización segura de last_processed
    - Lock para prevenir duplicados en ambientes multi-thread
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

        # 🔧 CORREGIDO: Inicializar en __init__ para evitar race condition
        self.last_processed = {}  # {symbol: (symbol, open_time, close_time)}
        self._processing_lock = asyncio.Lock()  # Lock para operaciones atómicas

    async def start(self):
        """Inicia la conexión y recibe los datos en tiempo real (sin duplicados)."""
        socket = None

        while self.keep_running:
            try:
                if not self.client:
                    self.client = await AsyncClient.create()
                    self.bsm = BinanceSocketManager(self.client, user_timeout=60)
                    logger.info("✅ Conectado a Binance WebSocket")

                if not socket:
                    streams = [f"{s}@kline_{self.interval}" for s in self.symbols]
                    logger.info(f"🔗 Iniciando streams: {streams}")
                    socket = self.bsm.multiplex_socket(streams)

                # Conexión abierta por while
                async with socket as s:
                    while self.keep_running:
                        try:
                            msg = await s.recv()
                            await self._process_message(msg)
                        except asyncio.TimeoutError:
                            logger.warning("⌛ Timeout, esperando siguiente mensaje...")
                            continue
                        except Exception as e:
                            logger.error(f"⚠️ Error recibiendo datos: {e}")
                            break

            except Exception as e:
                logger.error(f"⚠️ Error general del WebSocket: {e}")
                await asyncio.sleep(self.reconnect_delay)

                # Cerrar y reiniciar conexión completa
                if self.client:
                    await self.client.close_connection()
                    self.client = None
                    self.bsm = None
                    socket = None
                    logger.info("🔌 Cliente Binance cerrado, reiniciando...")

    async def _process_message(self, msg):
        """
        🔧 CORREGIDO: Procesamiento thread-safe con lock
        Previene race conditions en entornos con múltiples streams
        """
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

        # 🔧 CORREGIDO: Lock para garantizar atomicidad
        async with self._processing_lock:
            # Verificar si ya fue procesada
            if self.last_processed.get(symbol) == kline_id:
                logger.debug(f"⏭️ Vela duplicada ignorada: {symbol} {k['t']}")
                return

            # Marcar como procesada
            self.last_processed[symbol] = kline_id

        # Extraer datos relevantes
        kline_entry = [
            symbol,
            int(k["t"]),  # open_time
            int(k["T"]),  # close_time
            float(k["o"]),  # open
            float(k["c"]),  # close
            float(k["h"]),  # high
            float(k["l"]),  # low
            float(k["v"]),  # volume
        ]

        # Crear diccionario para este símbolo específico
        candle_data = {symbol: kline_entry}

        # Enviar al callback
        if self.on_update:
            try:
                await self.on_update(candle_data)
            except Exception as e:
                logger.error(f"⚠️ Error en callback on_update: {e}")

    async def stop(self):
        """Detiene la recolección de datos de forma limpia."""
        logger.info("🛑 Deteniendo recolección de datos...")
        self.keep_running = False

        if self.client:
            try:
                await self.client.close_connection()
                logger.info("✅ Conexión WebSocket cerrada correctamente")
            except Exception as e:
                logger.error(f"⚠️ Error cerrando conexión: {e}")

        # Limpiar referencias
        self.client = None
        self.bsm = None
        self.last_processed.clear()

    def get_stats(self) -> dict:
        """
        🔧 NUEVO: Obtiene estadísticas de procesamiento
        """
        return {
            "total_symbols": len(self.symbols),
            "processed_candles": len(self.last_processed),
            "is_running": self.keep_running,
            "last_processed": dict(self.last_processed)
        }