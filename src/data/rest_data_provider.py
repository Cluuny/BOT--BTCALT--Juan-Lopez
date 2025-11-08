# rest_data_provider.py

import time
from utils.logger import Logger
from typing import List, Optional, Dict, Any
from binance import Client, BinanceAPIException
import config.settings as settings

logger = Logger.get_logger(__name__)


class BinanceRESTClient:
    """
    Cliente REST para Binance Spot utilizando python-binance.
    Maneja autenticación y operaciones de trading/consulta.
    """

    def __init__(self, testnet: bool = True):
        logger.info("🔗 Conectando al cliente REST de Binance...")
        self.client = Client(
            settings.settings.API_KEY, settings.settings.API_SECRET, testnet=testnet
        )

        self._sync_time_with_server()
        self.client.ping()  # Prueba de conexión

        logger.info("✅ Cliente REST de Binance inicializado correctamente.")

    def _sync_time_with_server(self):
        """Sincroniza el tiempo local con el del servidor Binance de forma robusta."""
        try:
            server_time = self.client.get_server_time()["serverTime"]
            local_time = int(round(time.time() * 1000))
            self.time_offset = server_time - local_time
            self.client.TIME_OFFSET = self.time_offset  # Ajuste oficial

            logger.info(f"🕒 Desfase inicial detectado: {self.time_offset} ms")

            # --- Ajuste extra de seguridad: revalidar si el desfase supera 500 ms
            if abs(self.time_offset) > 500:
                logger.warning("⚠️ Desfase alto, intentando resync...")
                time.sleep(0.5)
                server_time = self.client.get_server_time()["serverTime"]
                local_time = int(round(time.time() * 1000))
                self.time_offset = server_time - local_time
                self.client.TIME_OFFSET = self.time_offset
                logger.info(f"✅ Resync aplicado: nuevo desfase {self.time_offset} ms")

            logger.info("⏱️ Sincronización completada correctamente.")

        except Exception as e:
            logger.error(
                f"⚠️ Error al sincronizar hora con el servidor de Binance: {e}"
            )

    # ======================
    # 🔹 ENDPOINTS PÚBLICOS
    # ======================

    def get_server_time(self) -> Dict[str, Any]:
        """Obtiene la hora del servidor."""
        return self.client.get_server_time()

    def get_exchange_info(self) -> Dict[str, Any]:
        """Obtiene información general del exchange."""
        return self.client.get_exchange_info()

    def get_symbol_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo."""
        logger.info(f"🔍 Consultando precio de {symbol.upper()}...")
        data = self.client.get_symbol_ticker(symbol=symbol.upper())
        return float(data["price"])

    def get_all_klines(
        self, list_symbols: List[str], interval: str = "1m", limit: int = 100
    ) -> Dict[str, List]:
        """Obtiene velas históricas (candlesticks) para múltiples símbolos."""
        all_klines = {}
        for symbol in list_symbols:
            klines = self.get_klines(symbol=symbol, interval=interval, limit=limit)
            all_klines[symbol] = klines
        return all_klines

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100):
        """Obtiene velas históricas - mantener formato CONSISTENTE con WebSocket"""
        symbol = symbol.upper()
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

        # 🔥 FORMATO CONSISTENTE: Usar LISTAS como WebSocket
        formatted_klines = []
        for k in klines:
            formatted_kline = [
                symbol,  # Índice 0: symbol
                int(k[0]),  # Índice 1: open_time
                int(k[6]),  # Índice 2: close_time
                float(k[1]),  # Índice 3: open
                float(k[4]),  # Índice 4: close (IMPORTANTE: usar close, no open)
                float(k[2]),  # Índice 5: high
                float(k[3]),  # Índice 6: low
                float(k[5]),  # Índice 7: volume
            ]
            formatted_klines.append(formatted_kline)

        return formatted_klines

    # ======================
    # 🔹 ENDPOINTS PRIVADOS
    # ======================

    def get_account_info(self) -> Dict[str, Any]:
        """Información general de la cuenta (balances, etc.)."""
        return self.client.get_account()

    def get_USDT_balance(self) -> float:
        """Obtiene el balance disponible de USDT."""
        return self.client.get_asset_balance(asset="USDT")  # Actualiza balances

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Consulta las órdenes abiertas (todas o de un símbolo)."""
        if symbol:
            return self.client.get_open_orders(symbol.upper())
        return self.client.get_open_orders()

    def create_order(
            self,
            symbol: str,
            side: str,
            type_: str,
            quantity: float,
            price: Optional[float] = None,
            time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """
        Crea una orden (MARKET o LIMIT).
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": quantity,
        }

        if type_.upper() == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        try:
            return self.client.create_order(**params)
        except BinanceAPIException as e:
            logger.error(f"❌ Error de API al crear orden: {e}")
            # Log adicional para debugging
            logger.error(f"📋 Parámetros de la orden: {params}")
            return {}
        except Exception as e:
            logger.error(f"❌ Error inesperado al crear orden: {e}")
            return {}


    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancela una orden por ID."""
        return self.client.cancel_order(symbol.upper(), orderId=order_id)
