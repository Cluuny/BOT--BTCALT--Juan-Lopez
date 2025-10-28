# rest_data_provider.py

import logging
from typing import List, Optional, Dict, Any
from binance import Client
import config.settings as settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class BinanceRESTClient:
    """
    Cliente REST para Binance Spot utilizando python-binance.
    Maneja autenticación y operaciones de trading/consulta.
    """

    def __init__(self):
        logging.info("🔗 Conectando al cliente REST de Binance...")
        self.client = Client(
            settings.settings.API_KEY, settings.settings.API_SECRET, testnet=True
        )
        logging.info("✅ Cliente REST de Binance inicializado correctamente.")

    # ======================
    # 🔹 ENDPOINTS PÚBLICOS
    # ======================

    def get_server_time(self) -> Dict[str, Any]:
        """Obtiene la hora del servidor."""
        return self.client.time()

    def get_exchange_info(self) -> Dict[str, Any]:
        """Obtiene información general del exchange."""
        return self.client.exchange_info()

    def get_symbol_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo."""
        logging.info(f"🔍 Consultando precio de {symbol.upper()}...")
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
        """Obtiene velas históricas (candlesticks)."""
        symbol = symbol.upper()
        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        klines = [
            {
                "symbol": symbol,
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
                "quote_asset_volume": float(k[7]),
                "number_of_trades": k[8],
                "taker_buy_base_asset_volume": float(k[9]),
                "taker_buy_quote_asset_volume": float(k[10]),
                "ignore": k[11],
            }
            for k in klines
        ]
        return klines

    # ======================
    # 🔹 ENDPOINTS PRIVADOS
    # ======================

    def get_account_info(self) -> Dict[str, Any]:
        """Información general de la cuenta (balances, etc.)."""
        return self.client.get_account()

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
        Ejemplo:
            client.create_order("BTCUSDT", "BUY", "MARKET", 0.001)
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

        return self.client.new_order(**params)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancela una orden por ID."""
        return self.client.cancel_order(symbol.upper(), orderId=order_id)
