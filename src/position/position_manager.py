from utils.logger import Logger
import time
import uuid
from typing import Any, Dict, List, Optional
from decimal import Decimal, ROUND_DOWN

from strategies.BaseStrategy import BaseStrategy
from data.rest_data_provider import BinanceRESTClient

logger = Logger.get_logger(__name__)


def is_valid_binance_response(response: dict) -> bool:
    """
    Valida si una respuesta de Binance es exitosa.

    Returns:
        True si la respuesta indica éxito, False en caso contrario
    """
    if response is None:
        return False

    # Si tiene código de error HTTP o mensaje de error, es inválida
    if "code" in response or "msg" in response:
        # Códigos positivos (200, etc.) pueden aparecer, verificar si es error
        code = response.get("code")
        if code and code < 0:  # Códigos negativos son errores en Binance
            return False

    # Si tiene orderId, es una respuesta válida de orden
    if "orderId" in response:
        return True

    # Si tiene status y no es error, es válida
    if "status" in response and "code" not in response:
        return True

    return False


class PositionManager:
    """
    🔧 VERSIÓN CORREGIDA: Gestión robusta de posiciones
    - Validación de minNotional
    - Protección contra division by zero
    - Manejo seguro de balance
    """

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
                        logger.info(f"📋 Info cacheada para {symbol}")
                        break

                if symbol not in self.symbols_info:
                    logger.warning(f"⚠️ No se encontró info para {symbol} en exchange")
                    return {}

            except Exception as e:
                logger.error(f"⚠️ Error obteniendo info del símbolo {symbol}: {e}")
                return {}
        return self.symbols_info.get(symbol, {})

    def _get_min_notional(self, symbol: str) -> float:
        """
        🔧 CORREGIDO: Extrae minNotional del símbolo (ambos formatos)
        Binance usa 'MIN_NOTIONAL' o 'NOTIONAL' según versión de API
        """
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            logger.warning(f"⚠️ No hay info de {symbol}, usando minNotional default=10")
            return 10.0

        filters = symbol_info.get('filters', [])

        # 🔧 NUEVO: Buscar ambos tipos de filtro
        for f in filters:
            filter_type = f.get('filterType')

            # Formato antiguo: MIN_NOTIONAL
            if filter_type == 'MIN_NOTIONAL':
                min_notional = float(f.get('minNotional', 10.0))
                logger.debug(f"📏 minNotional para {symbol}: {min_notional} USDT (MIN_NOTIONAL)")
                return min_notional

            # Formato nuevo: NOTIONAL
            elif filter_type == 'NOTIONAL':
                min_notional = float(f.get('minNotional', 10.0))
                logger.debug(f"📏 minNotional para {symbol}: {min_notional} USDT (NOTIONAL)")
                return min_notional

        # Fallback: Usar valor por defecto
        logger.warning(f"⚠️ MIN_NOTIONAL/NOTIONAL no encontrado para {symbol}, usando 10.0")
        logger.info(f"📋 Filtros disponibles: {[f.get('filterType') for f in filters]}")
        return 10.0

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
            logger.warning(f"⚠️ LOT_SIZE no encontrado para {symbol}")
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
        """
        🔧 CORREGIDO: Obtención robusta de balance
        """
        try:
            # 🔧 CORREGIDO: get_usdt_balance() ahora devuelve float directamente
            free_balance = self.rest_client.get_usdt_balance()

            # Validar que el balance sea positivo
            if free_balance < 0:
                logger.error(f"⚠️ Balance negativo detectado: {free_balance}")
                return 0.0

            logger.debug(f"💰 Balance USDT disponible: {free_balance:.2f}")
            return free_balance

        except Exception as e:
            logger.error(f"⚠️ Error obteniendo balance: {e}")
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
                logger.warning(
                    f"🚫 Límite de posiciones alcanzado ({total_open_orders}/{risk_params.max_open_positions})")
                return False

            return True
        except Exception as e:
            logger.error(f"⚠️ Error verificando posiciones abiertas: {e}")
            return False

    def build_market_order(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🔧 CORREGIDO: Construcción robusta de orden MARKET
        - Ahora permite override absoluto con signal['position_size_usdt']
        """
        try:
            symbol = signal["symbol"].upper()
            side = signal["type"].upper()
            risk_params = signal["risk_params"]

            # 1️⃣ Validar si se puede abrir posición
            if not self.can_open_position(symbol, risk_params):
                logger.warning("🚫 No se puede abrir posición (límite alcanzado)")
                return None

            # 2️⃣ Obtener balance disponible
            available_USDT_balance = self._get_available_USDT_balance()
            if available_USDT_balance <= 0:
                logger.warning(f"🚫 Balance insuficiente: {available_USDT_balance:.2f} USDT")
                return None

            # 3️⃣ Calcular cantidad a invertir
            # 🔧 CORREGIDO: get_symbol_price() → get_current_price()
            actual_symbol_price = self.rest_client.get_current_price(symbol=symbol)

            # 🔧 CORREGIDO: Protección contra division by zero
            if actual_symbol_price <= 0:
                logger.error(f"❌ Precio inválido para {symbol}: {actual_symbol_price}")
                return None

            # 🔧 CORREGIDO: Manejo consistente de risk_params (objeto o dict)
            signal_pos_usdt = signal.get('position_size_usdt')
            if signal_pos_usdt is not None:
                try:
                    quote_order_usdt = float(signal_pos_usdt)
                except Exception:
                    logger.error("❌ position_size_usdt inválido en señal")
                    return None
            else:
                # Extraer position_size de risk_params de forma segura
                if isinstance(risk_params, dict):
                    pos_frac = risk_params.get('position_size', 0.1)
                else:
                    pos_frac = getattr(risk_params, 'position_size', 0.1)

                try:
                    pos_frac = float(pos_frac)
                    if not (0 < pos_frac <= 1):
                        logger.error(f"❌ position_size fuera de rango (0,1]: {pos_frac}")
                        return None
                except Exception:
                    logger.error("❌ risk_params.position_size inválido")
                    return None

                quote_order_usdt = available_USDT_balance * pos_frac

            # 🔧 NUEVO: Validar minNotional ANTES de calcular quantity
            min_notional = self._get_min_notional(symbol)

            if quote_order_usdt < min_notional:
                logger.error(
                    f"🚫 Monto insuficiente: {quote_order_usdt:.2f} USDT < "
                    f"mínimo requerido {min_notional:.2f} USDT"
                )
                return None

            # Calcular cantidad en moneda base
            quote_order_qty = quote_order_usdt / actual_symbol_price

            # 4️⃣ Ajustar cantidad según LOT_SIZE
            adjusted_quantity = self._adjust_quantity_to_lot_size(symbol, quote_order_qty)

            if adjusted_quantity <= 0:
                logger.warning(f"🚫 Cantidad ajustada es 0 para {symbol}")
                return None

            # 🔧 NUEVO: Validación final de minNotional después de ajuste
            final_order_value = adjusted_quantity * actual_symbol_price
            if final_order_value < min_notional:
                logger.error(
                    f"🚫 Valor final de orden ({final_order_value:.2f} USDT) < "
                    f"minNotional ({min_notional:.2f} USDT) después de ajuste LOT_SIZE"
                )
                return None

            # 5️⃣ Armar orden
            order_params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": adjusted_quantity,
            }

            # 6️⃣ Guardar en registro local
            self.open_positions[symbol] = {
                "order_params": order_params,
                "timestamp": time.time(),
                "quote_order_usdt": quote_order_usdt,
                "expected_value_usdt": final_order_value,
            }

            logger.info(f"✅ Orden MARKET construida correctamente")
            logger.info(f"📋 {symbol} {side} qty={adjusted_quantity} valor≈{final_order_value:.2f} USDT")

            return order_params

        except KeyError as e:
            logger.error(f"⚠️ Clave faltante en la señal: {e}")
            return None
        except ZeroDivisionError as e:
            logger.error(f"❌ Error de división por cero: {e}")
            return None
        except Exception as e:
            logger.error(f"⚠️ Error construyendo orden: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def create_oco_orders(self, entry_response: dict, signal: Dict[str, Any]):
        """
        🔧 CORREGIDO: Crea órdenes OCO (TP + SL) con validación robusta
        """
        try:
            if not is_valid_binance_response(entry_response):
                logger.warning("🚫 No se crean OCOs: respuesta de entrada inválida")
                return

            symbol = signal["symbol"].upper()
            tp = signal.get('take_profit')
            sl = signal.get('stop_loss')

            if tp is None and sl is None:
                logger.debug("ℹ️ Señal no define TP ni SL; no se crean OCOs")
                return

            # Determinar cantidad ejecutada
            executed_qty = None
            try:
                executed_qty = float(entry_response.get("executedQty", 0) or 0)
            except Exception:
                executed_qty = None

            if not executed_qty or executed_qty <= 0:
                op = self.open_positions.get(symbol)
                if op:
                    executed_qty = op.get("order_params", {}).get("quantity")

            if not executed_qty or executed_qty <= 0:
                logger.warning("⚠️ No se pudo determinar cantidad ejecutada para crear OCO")
                return

            # Determinar side (invertir el lado de la entrada)
            side = "SELL" if signal.get("type", "BUY").upper() == "BUY" else "BUY"

            tp_price = float(tp) if tp is not None else None
            sl_price = float(sl) if sl is not None else None

            # 🔧 CORREGIDO: Crear Stop-Limit con stopPrice
            if tp_price is None and sl_price is not None:
                logger.info("🔧 Creando Stop-Limit (sin TP) como protección")
                # stopLimitPrice debe ser peor que stopPrice para garantizar ejecución
                sl_limit = sl_price * (0.995 if side == "SELL" else 1.005)

                resp = self.rest_client.create_order(
                    symbol=symbol,
                    side=side,
                    type_="STOP_LOSS_LIMIT",
                    quantity=executed_qty,
                    price=sl_limit,
                    time_in_force="GTC",
                    stop_price=sl_price  # 🔧 AGREGADO: parámetro faltante
                )

                if is_valid_binance_response(resp):
                    logger.info("✅ Stop-Limit creado")
                    self.open_positions.setdefault(symbol, {})["stop_limit"] = resp
                else:
                    logger.error(f"❌ Falló creación Stop-Limit: {resp}")
                return

            # Si solo TP existe, crear limit TP
            if tp_price is not None and sl_price is None:
                logger.info("🔧 Creando TAKE-PROFIT LIMIT (sin SL)")
                resp = self.rest_client.create_order(
                    symbol=symbol,
                    side=side,
                    type_="LIMIT",
                    quantity=executed_qty,
                    price=tp_price,
                    time_in_force="GTC",
                )
                if is_valid_binance_response(resp):
                    logger.info("✅ Take-Profit creado")
                    self.open_positions.setdefault(symbol, {})["take_profit"] = resp
                else:
                    logger.error(f"❌ Falló creación Take-Profit: {resp}")
                return

            # Si ambos existen, crear OCO
            logger.info("🔧 Intentando crear OCO (TP + SL)")
            stop_limit_price = sl_price * (0.999 if side == "SELL" else 1.001)

            oco_resp = self.rest_client.create_oco_order(
                symbol=symbol,
                side=side,
                quantity=executed_qty,
                take_profit_price=tp_price,
                stop_price=sl_price,
                stop_limit_price=stop_limit_price,
                stop_limit_time_in_force="GTC",
            )

            if is_valid_binance_response(oco_resp) or (
                isinstance(oco_resp, dict) and ("tp" in oco_resp or "sl" in oco_resp)
            ):
                logger.info("✅ OCO (o fallback) creada correctamente")
                self.open_positions.setdefault(symbol, {})["oco"] = oco_resp
            else:
                logger.error(f"❌ Falló creación OCO: {oco_resp}")

        except Exception as e:
            logger.error(f"⚠️ Error creando OCO: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_position_summary(self) -> Dict[str, Any]:
        """
        🔧 NUEVO: Obtiene resumen de posiciones abiertas
        """
        return {
            "total_positions": len(self.open_positions),
            "symbols": list(self.open_positions.keys()),
            "positions": self.open_positions
        }