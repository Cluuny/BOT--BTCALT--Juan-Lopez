from utils.logger import Logger
import time
import uuid
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_DOWN

from strategies.BaseStrategy import BaseStrategy
from data.rest_data_provider import BinanceRESTClient

logger = Logger.get_logger(__name__)


class PositionManager:
    def __init__(self, rest_client: Optional[BinanceRESTClient] = None):
        self.open_positions: Dict[str, Any] = {}
        self.rest_client = rest_client or BinanceRESTClient()
        self.symbols_info = {}  # Cache para información de símbolos

    def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Obtiene y cachea la información del símbolo con sus filtros de trading."""
        if symbol not in self.symbols_info:
            try:
                exchange_info = self.rest_client.get_exchange_info()
                for s in exchange_info['symbols']:
                    if s['symbol'] == symbol:
                        self.symbols_info[symbol] = s
                        break
            except Exception as e:
                logger.error(f"⚠️ Error obteniendo info del símbolo {symbol}: {e}")
                return {}
        return self.symbols_info.get(symbol, {})

    def _adjust_quantity_to_lot_size(self, symbol: str, quantity: float) -> float:
        """Ajusta la cantidad según los filtros LOT_SIZE del símbolo."""
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            logger.warning(f"⚠️ No se pudo obtener info de {symbol}, usando cantidad sin ajustar")
            return quantity

        # Buscar filtro LOT_SIZE
        lot_size_filter = None
        for f in symbol_info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                lot_size_filter = f
                break

        if not lot_size_filter:
            return quantity

        min_qty = float(lot_size_filter['minQty'])
        max_qty = float(lot_size_filter['maxQty'])
        step_size = float(lot_size_filter['stepSize'])

        # Ajustar a step size
        if step_size > 0:
            quantity = float(Decimal(str(quantity)) - Decimal(str(quantity)) % Decimal(str(step_size)))

        # Aplicar límites
        quantity = max(min_qty, min(max_qty, quantity))

        logger.info(f"🔢 Cantidad ajustada para {symbol}: {quantity} (step: {step_size})")
        return quantity

    def _get_available_USDT_balance(self) -> float:
        """Obtiene el balance disponible de USDT - VERSIÓN CORREGIDA"""
        try:
            balance_info = self.rest_client.get_USDT_balance()

            # 🔥 MANEJO CORRECTO: get_USDT_balance SIEMPRE retorna dict
            if balance_info is None:
                logger.warning("⚠️ No se encontró balance para USDT.")
                return 0.0

            if isinstance(balance_info, dict):
                free_balance = float(balance_info.get("free", 0.0))
                logger.debug(f"💰 Balance USDT disponible: {free_balance:.2f}")
                return free_balance
            else:
                # Caso inesperado - log de advertencia
                logger.warning(f"⚠️ Formato inesperado de balance: {type(balance_info)}")
                return 0.0

        except Exception as e:
            logger.error(f"⚠️ Error obteniendo balance disponible: {e}")
            return 0.0

    def can_open_position(
            self, symbol: str, risk_params: BaseStrategy.RiskParameters
    ) -> bool:
        """Verifica si se puede abrir una nueva posición según los parámetros de riesgo."""
        self.rest_client._sync_time_with_server()
        try:
            total_open_orders = len(self.rest_client.get_open_orders())
            logger.info(f"📊 Órdenes abiertas actualmente: {total_open_orders}")

            if total_open_orders >= risk_params.max_open_positions:
                logger.warning("🚫 Límite de posiciones abiertas alcanzado.")
                return False

            return True
        except Exception as e:
            logger.error(f"⚠️ Error verificando posiciones abiertas: {e}")
            return False

    def build_market_order(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Construye una orden MARKET basada en la señal recibida y los parámetros de riesgo.
        Devuelve un diccionario compatible con el método create_order de python-binance.
        """
        try:
            symbol = signal["symbol"].upper()
            side = signal["type"].upper()
            risk_params: BaseStrategy.RiskParameters = signal["risk_params"]

            # 1️⃣ Validar si se puede abrir una posición
            if not self.can_open_position(symbol, risk_params):
                return None

            # 2️⃣ Obtener balance disponible (por defecto en USDT)
            available_USDT_balance = self._get_available_USDT_balance()
            if available_USDT_balance <= 0:
                logger.warning("🚫 No hay balance disponible para abrir una posición.")
                return None

            # 3️⃣ Calcular cantidad a invertir en USDT
            actual_symbol_price = self.rest_client.get_symbol_price(symbol=symbol)
            quote_order_usdt = available_USDT_balance * risk_params.position_size

            # Para órdenes MARKET, necesitamos la cantidad en la moneda base
            quote_order_qty = quote_order_usdt / actual_symbol_price

            # 4️⃣ Ajustar cantidad según LOT_SIZE
            adjusted_quantity = self._adjust_quantity_to_lot_size(symbol, quote_order_qty)

            if adjusted_quantity <= 0:
                logger.warning(f"🚫 Cantidad ajustada es 0 para {symbol}")
                return None

            logger.info(
                f"💵 Tamaño de la posición: {quote_order_usdt:.2f} USDT -> {adjusted_quantity} {symbol.replace('USDT', '')}")

            # 5️⃣ Armar el diccionario con los parámetros compatibles con python-binance
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": adjusted_quantity,
            }

            # 6️⃣ Guardar en el registro local
            self.open_positions[symbol] = {
                "order_params": order_params,
                "timestamp": time.time(),
            }

            logger.info(f"✅ Orden MARKET construida correctamente: {order_params}")
            return order_params

        except KeyError as e:
            logger.error(f"⚠️ Clave faltante en la señal: {e}")
        except Exception as e:
            logger.error(f"⚠️ Error construyendo la orden: {e}")
        return None