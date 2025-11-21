from utils.logger import Logger
import time
from typing import Any, Dict, Optional, Union
from decimal import Decimal, ROUND_DOWN

from strategies.core.enhanced_base_strategy import EnhancedBaseStrategy, RiskParameters
from data.rest_data_provider import BinanceRESTClient
import asyncio

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
        # mapping para guardar detalles ejecutados por exchange
        self.executed_orders: Dict[str, Any] = {}

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

    def _adjust_quantity_to_lot_size(self, symbol: str, quantity: float) -> Decimal:
        """Ajusta la cantidad según los filtros LOT_SIZE del símbolo.
        Devuelve un Decimal ya cuantizado al stepSize para evitar notación científica
        y errores de formato al enviar al exchange.
        """
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            logger.warning(f"⚠️ No se pudo obtener info de {symbol}, usando cantidad sin ajustar")
            return Decimal(str(quantity))

        # Buscar filtro LOT_SIZE
        lot_size_filter = None
        for f in symbol_info.get('filters', []):
            if f.get('filterType') == 'LOT_SIZE':
                lot_size_filter = f
                break

        if not lot_size_filter:
            logger.warning(f"⚠️ LOT_SIZE no encontrado para {symbol}")
            return Decimal(str(quantity))

        # Usar Decimal para precisión
        min_qty = Decimal(str(lot_size_filter['minQty']))
        max_qty = Decimal(str(lot_size_filter['maxQty']))
        step_size = Decimal(str(lot_size_filter['stepSize']))

        q = Decimal(str(quantity))

        # Ajustar hacia abajo al múltiplo más cercano de step_size
        if step_size > Decimal('0'):
            try:
                multiplier = (q // step_size)
                q = multiplier * step_size
            except Exception:
                # Fallback básico
                q = (q / step_size).to_integral_value(rounding=ROUND_DOWN) * step_size

        # Aplicar límites
        if q < min_qty:
            q = min_qty
        if q > max_qty:
            q = max_qty

        logger.info(f"🔢 Cantidad ajustada para {symbol}: {q} (step: {step_size})")
        return q

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

    async def can_open_position(
            self, symbol: str, risk_params: Union[RiskParameters, Dict[str, Any]]
    ) -> bool:
        """Verifica si se puede abrir una nueva posición según los parámetros de riesgo."""
        # Extraer max_open_positions de dict u objeto
        try:
            if isinstance(risk_params, dict):
                max_open = int(risk_params.get('max_open_positions', 5))
            else:
                max_open = int(getattr(risk_params, 'max_open_positions', 5))
        except Exception:
            max_open = 5

        # Si el rest_client provee método async, usarlo
        try:
            if hasattr(self.rest_client, 'async_get_open_orders'):
                open_orders = await self.rest_client.async_get_open_orders(symbol=symbol)
            else:
                # Ejecutar en executor para no bloquear
                loop = asyncio.get_running_loop()
                open_orders = await loop.run_in_executor(None, self.rest_client.get_open_orders, symbol)

            total_open_orders = len(open_orders or [])
            logger.info(f"📊 Órdenes abiertas actualmente: {total_open_orders}")

            if total_open_orders >= max_open:
                logger.warning(
                    f"🚫 Límite de posiciones alcanzado ({total_open_orders}/{max_open})")
                return False

            return True
        except Exception as e:
            logger.error(f"⚠️ Error verificando posiciones abiertas: {e}")
            return False

    # Helper para recuperar precio con múltiples nombres soportados
    async def _retrieve_price_async(self, symbol: str) -> Optional[float]:
        """Intentar obtener precio usando la interfaz async o sync del cliente."""
        try:
            if hasattr(self.rest_client, 'async_get_current_price'):
                return await self.rest_client.async_get_current_price(symbol)
            if hasattr(self.rest_client, 'async_get_symbol_price'):
                return await self.rest_client.async_get_symbol_price(symbol)

            # fallback a sync en executor
            loop = asyncio.get_running_loop()
            if hasattr(self.rest_client, 'get_current_price'):
                return await loop.run_in_executor(None, self.rest_client.get_current_price, symbol)
            if hasattr(self.rest_client, 'get_symbol_price'):
                return await loop.run_in_executor(None, self.rest_client.get_symbol_price, symbol)
            # FakeRestClient compat (get_symbol_price)
            if hasattr(self.rest_client, 'get_symbol_price'):
                return await loop.run_in_executor(None, self.rest_client.get_symbol_price, symbol)
        except Exception as e:
            logger.error(f"Error obteniendo precio async: {e}")
        return None

    def _retrieve_price_sync(self, symbol: str) -> Optional[float]:
        """Intentar obtener precio usando interfaz sync del cliente (para tests sync)."""
        try:
            if hasattr(self.rest_client, 'get_current_price'):
                return self.rest_client.get_current_price(symbol)
            if hasattr(self.rest_client, 'get_symbol_price'):
                return self.rest_client.get_symbol_price(symbol)
            if hasattr(self.rest_client, 'get_symbol_price'):
                return self.rest_client.get_symbol_price(symbol)
            # FakeRestClient method
            if hasattr(self.rest_client, 'get_symbol_price'):
                return self.rest_client.get_symbol_price(symbol)
            # Some fakes expose get_symbol_price as lowercase
            if hasattr(self.rest_client, 'get_symbol_price'):
                return getattr(self.rest_client, 'get_symbol_price')(symbol)
        except Exception as e:
            logger.error(f"Error obteniendo precio sync: {e}")
        return None

    async def _retrieve_balance_async(self) -> float:
        try:
            if hasattr(self.rest_client, 'async_get_usdt_balance'):
                return await self.rest_client.async_get_usdt_balance()

            loop = asyncio.get_running_loop()
            if hasattr(self.rest_client, 'get_usdt_balance'):
                return await loop.run_in_executor(None, self.rest_client.get_usdt_balance)
            if hasattr(self.rest_client, 'get_USDT_balance'):
                # fake client returns dict
                info = await loop.run_in_executor(None, self.rest_client.get_USDT_balance)
                return float(info.get('free', 0))
        except Exception as e:
            logger.error(f"Error obteniendo balance async: {e}")
        return 0.0

    def _retrieve_balance_sync(self) -> float:
        try:
            if hasattr(self.rest_client, 'get_usdt_balance'):
                return self.rest_client.get_usdt_balance()
            if hasattr(self.rest_client, 'get_USDT_balance'):
                info = self.rest_client.get_USDT_balance()
                return float(info.get('free', 0))
        except Exception as e:
            logger.error(f"Error obteniendo balance sync: {e}")
        return 0.0

    # Mantener compatibilidad: wrapper sincrónico que ejecuta la versión async si no hay loop
    def build_market_order(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wrapper síncrono para compatibilidad con tests y código existente.
        Si hay un event loop en ejecución, devuelve la coroutine (llamar desde código async en ese caso).
        """
        # Preferir get_running_loop para evitar DeprecationWarning en Python >=3.10
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Si hay un loop corriendo, retornar la coroutine para que el caller la await
            return self._build_market_order_async(signal)

        # No hay loop en ejecución: crear un loop temporal para ejecutar la coroutine
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(self._build_market_order_async(signal))
        finally:
            new_loop.close()

    async def _build_market_order_async(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Implementación asíncrona real de build_market_order (interna).
        """
        try:
            symbol = signal["symbol"].upper()
            side = signal["type"].upper()
            risk_params = signal["risk_params"]

            # 1️⃣ Validar si se puede abrir posición
            can_open = await self.can_open_position(symbol, risk_params)
            if not can_open:
                logger.warning("🚫 No se puede abrir posición (límite alcanzado)")
                return None

            # 2️⃣ Obtener balance disponible
            try:
                available_USDT_balance = await self._retrieve_balance_async()
            except Exception as e:
                logger.error(f"⚠️ Error obteniendo balance async: {e}")
                available_USDT_balance = 0.0

            if available_USDT_balance <= 0:
                logger.warning(f"🚫 Balance insuficiente: {available_USDT_balance:.2f} USDT")
                return None

            # 3️⃣ Calcular cantidad a invertir (precio)
            try:
                actual_symbol_price = await self._retrieve_price_async(symbol)
            except Exception as e:
                logger.error(f"❌ Error obteniendo precio de mercado para {symbol}: {e}")
                return None

            if actual_symbol_price is None or actual_symbol_price <= 0:
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

            # 4️⃣ Ajustar cantidad según LOT_SIZE (ahora Decimal)
            adjusted_quantity = self._adjust_quantity_to_lot_size(symbol, quote_order_qty)

            if adjusted_quantity <= Decimal('0'):
                logger.warning(f"🚫 Cantidad ajustada es 0 para {symbol}")
                return None

            # 🔧 NUEVO: Validación final de minNotional después de ajuste (usar Decimal)
            actual_price_dec = Decimal(str(actual_symbol_price))
            final_order_value = (adjusted_quantity * actual_price_dec)
            if final_order_value < Decimal(str(min_notional)):
                logger.error(
                    f"🚫 Valor final de orden ({float(final_order_value):.2f} USDT) < "
                    f"minNotional ({min_notional:.2f} USDT) después de ajuste LOT_SIZE"
                )
                return None

            # Formatear la cantidad como string sin notación científica respetando stepSize
            # Recuperar stepSize para formateo
            step_size_str = None
            sym_info = self._get_symbol_info(symbol)
            for f in sym_info.get('filters', []):
                if f.get('filterType') == 'LOT_SIZE':
                    step_size_str = str(f.get('stepSize'))
                    break

            if step_size_str is None:
                # Fallback: usar 8 decimales
                step_size = Decimal('0.00000001')
            else:
                step_size = Decimal(step_size_str)

            try:
                quantized = (adjusted_quantity // step_size) * step_size
            except Exception:
                quantized = adjusted_quantity

            # format with fixed point representation to avoid exponent notation
            quantity_str = format(quantized.normalize(), 'f')

            order_params = {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                # quantity compatible para código interno/tests
                "quantity": float(quantized),
                # quantity_str para el exchange (precisión y formato exacto)
                "quantity_str": quantity_str,
            }

            # Nota: NO registrar la posición en open_positions aquí.
            # El registro debe realizarse solo cuando el exchange confirme la ejecución
            # para evitar que la estrategia marque una posición como ABIERTA cuando la orden falla.
            # La TradeEngine es responsable de registrar posiciones tras respuesta positiva del exchange.

            logger.info(f"✅ Orden MARKET construida correctamente")
            logger.info(f"📋 {symbol} {side} qty={quantity_str} valor≈{float(final_order_value):.2f} USDT")

            return order_params

        except Exception as e:
            logger.error(f"⚠️ Error construyendo orden: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def register_open_position(self, symbol: str, order_response: Dict[str, Any], expected_value_usdt: float, executed_qty: float | None = None, avg_price: float | None = None):
        """Registrar posición como abierta tras confirmación del exchange.

        Parámetros:
            - symbol: símbolo (ej. 'BTCUSDT')
            - order_response: respuesta del exchange (dict) o parametros de orden
            - expected_value_usdt: valor estimado en USDT
        """
        try:
            # Extraer qty (origQty / executedQty / quantity) si no fue provisto
            qty = executed_qty
            if qty is None and isinstance(order_response, dict):
                try:
                    qty = float(order_response.get('executedQty') or order_response.get('origQty') or order_response.get('quantity') or 0)
                except Exception:
                    qty = None

            # Extraer avg_price si no fue provisto
            ap = avg_price
            if ap is None and isinstance(order_response, dict):
                # intentar derivar avg_price de cummulativeQuoteQty / executedQty
                try:
                    cumm_quote = float(order_response.get('cummulativeQuoteQty', 0) or 0)
                    exec_q = float(order_response.get('executedQty', qty or 0) or 0)
                    if exec_q > 0 and cumm_quote > 0:
                        ap = cumm_quote / exec_q
                except Exception:
                    ap = None

            # Guardar en estructuras internas
            self.open_positions[symbol] = {
                'order_response': order_response,
                'timestamp': time.time(),
                'executed_qty': float(qty) if qty is not None else None,
                'avg_price': float(ap) if ap is not None else None,
                'expected_value_usdt': float(expected_value_usdt)
            }
            logger.info(f"📌 Posición registrada en PositionManager para {symbol}: qty={qty} avg_price={ap}")
        except Exception as e:
            logger.error(f"⚠️ Error registrando posición: {e}")

    async def create_oco_orders(self, entry_response: dict, signal: Dict[str, Any]):
        """Crear OCO (TP+SL) o TP/SL por separado usando el rest_client.

        entry_response: respuesta de la orden de entrada (puede contener executedQty)
        signal: dic con 'take_profit' y 'stop_loss'
        """
        try:
            symbol = signal.get('symbol')
            if symbol is None:
                logger.warning("⚠️ create_oco_orders: signal sin symbol")
                return

            tp = signal.get('take_profit')
            sl = signal.get('stop_loss')

            if tp is None and sl is None:
                logger.debug("ℹ️ Señal sin TP ni SL; no se crearán OCOs")
                return

            # Determinar quantity ejecutada
            executed_qty = None
            try:
                executed_qty = float(entry_response.get('executedQty', 0) or 0)
            except Exception:
                executed_qty = None

            # si no viene, intentar desde open_positions (registered executed_qty)
            if (not executed_qty or executed_qty <= 0) and symbol in self.open_positions:
                executed_qty = self.open_positions[symbol].get('executed_qty')

            if not executed_qty or executed_qty <= 0:
                logger.warning(f"⚠️ No se pudo determinar cantidad ejecutada para crear OCO en {symbol}")
                return

            side = 'SELL' if signal.get('type', 'BUY').upper() == 'BUY' else 'BUY'

            # Preferir create_oco_order si está disponible
            if hasattr(self.rest_client, 'create_oco_order'):
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, self.rest_client.create_oco_order,
                                                  symbol, side, executed_qty, float(tp) if tp is not None else None, float(sl) if sl is not None else None, None)
                # guardar fallback
                if isinstance(resp, dict):
                    self.open_positions.setdefault(symbol, {})['oco'] = resp
                    logger.info(f"✅ OCO creada para {symbol}: {resp}")
                else:
                    logger.warning(f"⚠️ Respuesta inesperada create_oco_order para {symbol}: {resp}")
                return

            # Fallback: crear TP y SL por separado
            logger.info("ℹ️ create_oco_orders: create_oco_order no disponible, creando TP/SL por separado")
            if tp is not None:
                loop = asyncio.get_running_loop()
                tp_resp = await loop.run_in_executor(None, self.rest_client.create_order,
                                                      symbol, side, 'LIMIT', executed_qty, float(tp))
                if tp_resp:
                    self.open_positions.setdefault(symbol, {})['take_profit'] = tp_resp

            if sl is not None:
                # stop_limit_price: ajustar pequeño margen
                sl_limit = float(sl) * 1.0
                loop = asyncio.get_running_loop()
                sl_resp = await loop.run_in_executor(None, self.rest_client.create_order,
                                                      symbol, side, 'STOP_LOSS_LIMIT', executed_qty, sl_limit)
                if sl_resp:
                    self.open_positions.setdefault(symbol, {})['stop_limit'] = sl_resp

        except Exception as e:
            logger.error(f"⚠️ Error creando OCO en PositionManager: {e}")
            import traceback
            logger.error(traceback.format_exc())
