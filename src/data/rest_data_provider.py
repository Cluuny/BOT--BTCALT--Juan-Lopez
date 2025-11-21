# rest_data_provider.py

import time
import os
from utils.logger import Logger
from typing import List, Optional, Dict, Any
from binance import Client, BinanceAPIException
import config.settings as settings
import asyncio
from functools import partial

logger = Logger.get_logger(__name__)


class BinanceRESTClient:
    """
    Cliente REST para Binance Spot utilizando python-binance.
    Maneja autenticación y operaciones de trading/consulta.
    """

    def __init__(self):
        logger.info("🔗 Conectando al cliente REST de Binance...")
        # Validar claves antes de instanciar el cliente (permite importar settings sin crash)
        settings.settings.validate_api_keys()

        if settings.settings.MODE == "TESNET":
            is_tesnet = True
        elif settings.settings.MODE == "REAL":
            is_tesnet = False
        else:
            raise Exception("Invalid MODE in settings")

        self.client = Client(
            settings.settings.API_KEY, settings.settings.API_SECRET, testnet=is_tesnet
        )

        self._sync_time_with_server()
        self.client.ping()  # Prueba de conexión

        # Rate limiting básico
        self._min_interval = float(os.getenv("REST_MIN_INTERVAL_SECONDS", "0.1"))
        self._last_request_time = 0.0

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
            logger.error(f"⚠️ Error al sincronizar hora con el servidor de Binance: {e}")

    def _throttle(self):
        """Rate limiting simple: espera si la última llamada fue reciente."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request_with_retries(self, func, max_attempts: int = 3, initial_backoff: float = 0.5, *args, **kwargs):
        """Helper para reintentos con backoff exponencial y throttle."""
        attempt = 0
        backoff = initial_backoff
        while attempt < max_attempts:
            try:
                self._throttle()
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                logger.warning(f"⚠️ BinanceAPIException (intento {attempt+1}): {e}")
                attempt += 1
                if attempt >= max_attempts:
                    logger.error(f"❌ Máximos reintentos alcanzados: {e}")
                    raise
                time.sleep(backoff)
                backoff *= 2
            except Exception as e:
                logger.warning(f"⚠️ Excepción en request (intento {attempt+1}): {e}")
                attempt += 1
                if attempt >= max_attempts:
                    logger.error(f"❌ Máximos reintentos alcanzados (general): {e}")
                    raise
                time.sleep(backoff)
                backoff *= 2

    # ======================
    # 🔹 ENDPOINTS PÚBLICOS
    # ======================

    def get_server_time(self) -> Dict[str, Any]:
        """Obtiene la hora del servidor."""
        return self.client.get_server_time()

    def get_price_change_percent(self, symbol: str) -> float:
        """Obtiene el porcentaje de cambio de precio actual."""
        return float(self.client.get_ticker(symbol=symbol.upper())["priceChangePercent"])

    def get_exchange_info(self) -> Dict[str, Any]:
        """Obtiene información general del exchange."""
        return self.client.get_exchange_info()

    def get_symbol_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo."""
        logger.info(f"🔍 Consultando precio de {symbol.upper()}...")
        data = self.client.get_symbol_ticker(symbol=symbol.upper())
        return float(data["price"])

    # Alias para compatibilidad con código existente
    def get_current_price(self, symbol: str) -> float:
        return self.get_symbol_price(symbol)

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

    def get_usdt_balance(self) -> float:
        """Obtiene el balance disponible de USDT."""
        balance_info = self.client.get_asset_balance(asset="USDT")
        if balance_info:
            return float(balance_info.get("free", 0.0))
        return 0.0

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Consulta las órdenes abiertas (todas o de un símbolo)."""
        # Fix: pasar symbol al client si se provee
        if symbol:
            return self.client.get_open_orders(symbol=symbol.upper())
        return self.client.get_open_orders()

    def create_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una orden (MARKET o LIMIT) con reintentos y rate limiting.
        Devuelve dict de respuesta o None en caso de error.
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
            resp = self._request_with_retries(lambda **p: self.client.create_order(**p), max_attempts=3, initial_backoff=0.5, **params)
            return resp
        except BinanceAPIException as e:
            logger.error(f"❌ Error de API al crear orden: {e}")
            logger.error(f"📋 Parámetros de la orden: {params}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado al crear orden: {e}")
            return None

    def create_oco_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit_price: float,
        stop_price: float,
        stop_limit_price: Optional[float] = None,
        stop_limit_time_in_force: str = "GTC",
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una OCO (Take-Profit Limit + Stop-Limit) si la API lo soporta.
        Si python-binance no provee create_oco_order, hace fallback creando TP y SL por separado.
        """
        symbol = symbol.upper()
        try:
            sl_limit = stop_limit_price if stop_limit_price is not None else stop_price
            params = {
                "symbol": symbol,
                "side": side.upper(),
                "quantity": quantity,
                "price": take_profit_price,
                "stopPrice": stop_price,
                "stopLimitPrice": sl_limit,
                "stopLimitTimeInForce": stop_limit_time_in_force,
            }

            if hasattr(self.client, "create_oco_order"):
                resp = self._request_with_retries(
                    lambda: self.client.create_oco_order(**params),
                    max_attempts=3,
                    initial_backoff=0.5
                )
                return resp
            else:
                # Fallback: crear TP y SL por separado (LIMIT + STOP_LOSS_LIMIT)
                logger.info("ℹ️ create_oco_order no disponible en client, creando TP y SL por separado")
                tp_resp = self.create_order(symbol=symbol, side=side, type_="LIMIT", quantity=quantity, price=take_profit_price)

                # Para STOP_LOSS_LIMIT necesitamos tanto stopPrice como price
                sl_params = {
                    "symbol": symbol,
                    "side": side.upper(),
                    "type": "STOP_LOSS_LIMIT",
                    "quantity": quantity,
                    "price": sl_limit,
                    "stopPrice": stop_price,
                    "timeInForce": stop_limit_time_in_force,
                }
                sl_resp = self._request_with_retries(
                    lambda: self.client.create_order(**sl_params),
                    max_attempts=3,
                    initial_backoff=0.5
                )

                # devolver un diccionario agregado para indicar éxito parcial/total
                result = {"tp": tp_resp, "sl": sl_resp}
                return result
        except BinanceAPIException as e:
            logger.error(f"❌ Error creando OCO en Binance: {e}")
            logger.error(f"📋 Parámetros OCO: {params}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado creando OCO: {e}")
            return None

    def cancel_order(self, symbol: str, order_id: int) -> Optional[Dict[str, Any]]:
        """Cancela una orden por ID con reintentos."""
        try:
            resp = self._request_with_retries(
                lambda: self.client.cancel_order(symbol=symbol.upper(), orderId=order_id),
                max_attempts=3,
                initial_backoff=0.3
            )
            return resp
        except Exception as e:
            logger.error(f"❌ Error cancelando orden: {e}")
            return None

    # =============
    # Async helpers
    # =============
    async def async_run_in_executor(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        # usar functools.partial para pasar correctamente args/kwargs
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def async_get_current_price(self, symbol: str) -> float:
        return await self.async_run_in_executor(self.get_current_price, symbol)

    async def async_get_symbol_price(self, symbol: str) -> float:
        return await self.async_get_current_price(symbol)

    async def async_get_klines(self, symbol: str, interval: str = "1m", limit: int = 100):
        return await self.async_run_in_executor(self.get_klines, symbol, interval, limit)

    async def async_get_all_klines(self, list_symbols: List[str], interval: str = "1m", limit: int = 100):
        return await self.async_run_in_executor(self.get_all_klines, list_symbols, interval, limit)

    async def async_get_account_info(self) -> Dict[str, Any]:
        return await self.async_run_in_executor(self.get_account_info)

    async def async_get_usdt_balance(self) -> float:
        return await self.async_run_in_executor(self.get_usdt_balance)

    async def async_get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self.async_run_in_executor(self.get_open_orders, symbol)

    async def async_create_order(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return await self.async_run_in_executor(self.create_order, *args, **kwargs)

    async def async_create_oco_order(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return await self.async_run_in_executor(self.create_oco_order, *args, **kwargs)

    async def async_cancel_order(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        return await self.async_run_in_executor(self.cancel_order, *args, **kwargs)

