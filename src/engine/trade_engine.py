import asyncio
import traceback
import time

from utils.logger import Logger
from position.position_manager import PositionManager

from strategies.BaseStrategy import BaseStrategy
from contracts.signal_contract import ValidatedSignal, SignalContract
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.order_repository import OrderRepository
from persistence.repositories.fill_repository import FillRepository
from persistence.repositories.balance_snapshot_repository import BalanceSnapshotRepository
from persistence.repositories.signal_repository import SignalRepository
from persistence.repositories.log_repository import LogRepository
from persistence.repositories.account_repository import AccountRepository

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


class TradeEngine:
    """
    🔧 VERSIÓN CORREGIDA: Validación robusta de respuestas de Binance
    """

    def __init__(self, signal_queue: asyncio.Queue, bot_id: int, run_db_id: int | None = None, rest_client: BinanceRESTClient | None = None):
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        # permitir inyección de rest_client para tests
        self.rest_client = rest_client or BinanceRESTClient(testnet=False)
        self.position_manager = PositionManager(rest_client=self.rest_client)
        self.order = None

    async def start(self):
        """Escucha continuamente la cola de señales VALIDADAS."""
        logger.info("🚀 Trade Engine iniciado - Esperando señales validadas...")

        # 🟠 IMPORTANTE: sincronizar órdenes abiertas y estado en startup
        try:
            await self._sync_open_orders_on_startup()
        except Exception as e:
            logger.warning(f"⚠️ No se pudo sincronizar órdenes al startup: {e}")

        while True:
            raw_signal = await self.signal_queue.get()

            # Validar señal
            validated_signal = ValidatedSignal.create_safe_signal(raw_signal)

            if validated_signal is None:
                logger.error("❌ Señal descartada por no cumplir contrato")
                logger.error(f"📋 Señal inválida: {raw_signal}")
                self.signal_queue.task_done()
                continue

            logger.info(f"📡 TradeEngine recibió señal VALIDADA")
            logger.debug(f"🔍 Detalles señal: {validated_signal}")

            await self.handle_signal(validated_signal)
            self.signal_queue.task_done()

    async def _sync_open_orders_on_startup(self):
        """
        Sincroniza órdenes abiertas desde Binance y las registra en PositionManager.open_positions.
        """
        try:
            # usar versión async si está disponible
            if hasattr(self.rest_client, 'async_get_open_orders'):
                open_orders = await self.rest_client.async_get_open_orders()
            else:
                loop = asyncio.get_running_loop()
                open_orders = await loop.run_in_executor(None, self.rest_client.get_open_orders)

            logger.info(f"🔁 Sincronizando {len(open_orders)} órdenes abiertas desde exchange")
            for o in open_orders:
                symbol = o.get("symbol")
                if not symbol:
                    continue
                # Mapear a estructura simple que PositionManager espera
                params = {
                    "order_params": {
                        "symbol": symbol,
                        "side": o.get("side"),
                        "type": o.get("type"),
                        "quantity": float(o.get("origQty", o.get("quantity", 0)) or 0),
                    },
                    "timestamp": time.time(),
                    "quote_order_usdt": None,
                    "expected_value_usdt": None,
                    "exchange_order": o,
                }
                self.position_manager.open_positions[symbol] = params
            logger.info("✅ Sincronización inicial de órdenes completa")
        except Exception as e:
            logger.warning(f"⚠️ Error sincronizando órdenes abiertas: {e}")

    async def handle_signal(self, signal: SignalContract):
        """Procesa señales que cumplen el contrato"""
        try:
            strategy_name = signal.get('strategy_name', 'Desconocida')
            symbol = signal['symbol']
            signal_type = signal['type']
            price = signal['price']
            risk_params = signal.get('risk_params', {})

            # 🔎 Validar desviación de precio entre señal y mercado
            try:
                # usar método async preferentemente
                if hasattr(self.rest_client, 'async_get_current_price'):
                    market_price = await self.rest_client.async_get_current_price(symbol)
                else:
                    loop = asyncio.get_running_loop()
                    market_price = await loop.run_in_executor(None, self.rest_client.get_current_price, symbol)

                max_dev = None
                # intentar leer umbral desde risk_params
                if isinstance(risk_params, dict):
                    max_dev = risk_params.get("max_price_deviation")
                else:
                    max_dev = getattr(risk_params, "max_price_deviation", None)
                max_dev = float(max_dev) if max_dev is not None else 0.05  # default 5%

                deviation = abs(price - market_price) / market_price
                if deviation > max_dev:
                    logger.warning(f"🚫 Señal descartada por desviación de precio ({deviation:.3f} > {max_dev:.3f})")
                    return
            except Exception as e:
                logger.warning(f"⚠️ No se pudo validar desviación de precio: {e}")

            logger.info(f"🔔 Procesando señal validada | Estrategia: {strategy_name}")
            logger.info(f"   Símbolo: {symbol} | Tipo: {signal_type} | Precio: {price:.2f}")

            if signal_type == "BUY":
                await self._handle_buy(signal=signal)
            elif signal_type == "SELL":
                await self._handle_sell(signal=signal)
            else:
                logger.error(f"❌ Tipo de señal desconocido: {signal_type}")

        except KeyError as e:
            logger.error(f"❌ Error en señal validada (faltan campos): {e}")
            logger.error(f"📋 Señal: {signal}")
        except Exception as e:
            logger.error(f"❌ Error inesperado en handle_signal: {e}")
            logger.error(f"📋 Traceback: {traceback.format_exc()}")

    async def _persist_order_and_fills(self, request_payload: dict, response: dict,
                                 symbol: str, side: str, order_type: str, quantity: float):
        """
        🔧 CORREGIDO: Persistencia con validación de respuesta
        """
        session = db.get_session()
        try:
            order_repo = OrderRepository(session)
            fill_repo = FillRepository(session)
            balance_repo = BalanceSnapshotRepository(session)
            signal_repo = SignalRepository(session)
            log_repo = LogRepository(session)
            account_repo = AccountRepository(session)

            # Vincular con última señal
            latest_signal = None
            try:
                latest_signal = signal_repo.get_latest_by_symbol(bot_id=self.bot_id, symbol=symbol)
            except Exception as e:
                logger.warning(f"No se pudo vincular con señal: {e}")

            # 🔧 CORREGIDO: Manejar respuestas None y de error
            if response is None:
                exchange_order_id = "ERROR_NO_RESPONSE"
                status = "REJECTED"
                error_msg = "No se recibió respuesta del exchange"
                is_error = True
            else:
                is_error = not is_valid_binance_response(response)

                if is_error:
                    # Orden falló en Binance
                    exchange_order_id = "ERROR"
                    status = "REJECTED"
                    error_msg = response.get("msg", str(response))
                else:
                    # Orden exitosa
                    exchange_order_id = str(response.get("orderId"))
                    status = response.get("status", "NEW")
                    error_msg = None

            # Crear registro de orden
            order = order_repo.create(
                bot_id=self.bot_id,
                signal_id=(latest_signal.id if latest_signal else None),
                exchange_order_id=exchange_order_id,
                symbol=symbol,
                side=side,
                type=order_type,
                price=request_payload.get("price"),
                quantity=quantity,
                status=status,
                run_id=self.run_db_id,
                client_order_id=response.get("clientOrderId") if not is_error and response else None,
                time_in_force=response.get("timeInForce") if not is_error and response else None,
                request_payload=request_payload,
            )

            # Guardar payload y errores
            order_repo.set_exchange_payload(
                order_id=order.id,
                exchange_response=response if response else {},
                last_error=error_msg
            )

            # Log en BD (con manejo de excepciones)
            try:
                log_level = "ERROR" if is_error else "INFO"
                log_message = (
                    f"Orden rechazada {symbol} {side}: {error_msg}" if is_error
                    else f"Orden creada {symbol} {side} {order_type} qty={quantity} status={status}"
                )

                log_repo.add_log(
                    bot_id=self.bot_id,
                    run_id=self.run_db_id,
                    level=log_level,
                    component="engine",
                    correlation_id=str(order.id),
                    message=log_message,
                    context={"request": request_payload, "response": response if response else {}},
                )
            except Exception as log_error:
                # No fallar por error de logging
                logger.warning(f"⚠️ No se pudo guardar log en BD: {log_error}")

            # Si la orden falló, no continuar con fills
            if is_error:
                logger.error(f"💥 Orden rechazada por Binance: {error_msg}")
                return

            # Procesar fills (solo si orden exitosa)
            fills = response.get("fills") or []
            total_quote = 0.0
            total_qty = 0.0

            for f in fills:
                price = float(f.get("price", 0) or 0)
                qty = float(f.get("qty", 0) or 0)
                quote_qty = float(f.get("quoteQty", price * qty))
                commission = float(f.get("commission", 0) or 0)
                commission_asset = f.get("commissionAsset")
                is_maker = bool(f.get("isMaker", False))
                trade_id = str(f.get("tradeId")) if f.get("tradeId") is not None else None

                fill_repo.add(
                    order_id=order.id,
                    price=price,
                    qty=qty,
                    quote_qty=quote_qty,
                    commission=commission,
                    commission_asset=commission_asset,
                    is_maker=is_maker,
                    trade_id=trade_id,
                )
                total_quote += quote_qty
                total_qty += qty

            # Actualizar cantidades ejecutadas
            executed_qty = float(response.get("executedQty", total_qty))
            cummulative_quote_qty = float(response.get("cummulativeQuoteQty", total_quote))
            avg_price = (cummulative_quote_qty / executed_qty) if executed_qty > 0 else None

            order_repo.update_exec_quantities(
                order_id=order.id,
                executed_qty=executed_qty,
                cummulative_quote_qty=cummulative_quote_qty,
                avg_price=avg_price,
            )

            # Marcar orden como finalizada si corresponde
            final_status = response.get("status")
            if final_status in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
                try:
                    order_repo.set_is_working(order_id=order.id, is_working=False)
                except Exception:
                    pass

            # Snapshot de balance si orden completamente FILLED
            if final_status == "FILLED":
                try:
                    # usar versión async si está disponible
                    if hasattr(self.rest_client, 'async_get_account_info'):
                        acct = await self.rest_client.async_get_account_info()
                    else:
                        loop = asyncio.get_running_loop()
                        acct = await loop.run_in_executor(None, self.rest_client.get_account_info)

                    # Resumen de cuenta
                    try:
                        account_id = acct.get("accountType", "SPOT")
                        account_repo.create_or_update(
                            exchange="BINANCE",
                            account_id=account_id,
                            balance_total=0.0,
                            balance_available=0.0,
                            account_type=acct.get("accountType", "SPOT"),
                            can_trade=True,
                            maker_commission=float(acct.get("makerCommission", 0) or 0),
                            taker_commission=float(acct.get("takerCommission", 0) or 0),
                            permissions=acct.get("permissions"),
                        )
                    except Exception as acc_err:
                        logger.warning(f"⚠️ Error guardando account: {acc_err}")

                    # Snapshots de balances
                    balances = acct.get("balances", [])
                    for b in balances:
                        asset = b.get("asset")
                        free = float(b.get("free", 0) or 0)
                        locked = float(b.get("locked", 0) or 0)
                        balance_repo.add(bot_id=self.bot_id, asset=asset, free=free, locked=locked)

                except Exception as snap_err:
                    logger.error(f"Error tomando BalanceSnapshot: {snap_err}")

            logger.info(f"💾 Orden {order.id} persistida correctamente")

        except Exception as e:
            logger.error(f"❌ Error persistiendo orden: {e}")
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
        finally:
            session.close()

    async def _handle_buy(self, signal: SignalContract):
        """Maneja compra con señal validada"""
        try:
            rsi_value = signal.get('rsi')
            position_size = signal.get('position_size_usdt')
            reason = signal.get('reason', 'Sin razón')
            strategy_name = signal.get('strategy_name', 'Desconocida')

            rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "N/A"
            position_str = f"{position_size:.2f}" if position_size is not None else "N/A"

            logger.info(
                f"🟢 COMPRA | {signal['symbol']} @ {signal['price']:.2f} | "
                f"RSI: {rsi_str} | Tamaño: {position_str} USDT | "
                f"Estrategia: {strategy_name} | Razón: {reason}"
            )

            # build_market_order es ahora async
            self.order = await self.position_manager.build_market_order(signal=signal)

            if self.order is None:
                logger.warning("⚠️ No se pudo construir orden de compra")
                return

            logger.info(f"📦 Ejecutando orden: {self.order}")

            # Ejecutar orden (usar async si disponible)
            if hasattr(self.rest_client, 'async_create_order'):
                response = await self.rest_client.async_create_order(
                    symbol=self.order['symbol'],
                    side=self.order['side'],
                    type_=self.order['type'],
                    quantity=self.order['quantity'],
                )
            else:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, self.rest_client.create_order,
                                                      self.order['symbol'], self.order['side'], self.order['type'], self.order['quantity'])

            # Validar respuesta antes de persistir
            if response is None:
                logger.error(f"❌ No se recibió respuesta del exchange")
                is_valid = False
            else:
                is_valid = is_valid_binance_response(response)
                if is_valid:
                    logger.info(f"✅ Orden ejecutada exitosamente")
                    logger.debug(f"📋 Respuesta: {response}")
                else:
                    logger.error(f"❌ Orden rechazada por Binance")
                    logger.error(f"📋 Respuesta: {response}")

            # Persistir siempre (éxito o error)
            await self._persist_order_and_fills(
                request_payload={
                    "symbol": self.order['symbol'],
                    "side": self.order['side'],
                    "type": self.order['type'],
                    "quantity": self.order['quantity']
                },
                response=response,
                symbol=self.order['symbol'],
                side=self.order['side'],
                order_type=self.order['type'],
                quantity=self.order['quantity'],
            )

            # 🟠 Si la orden fue exitosa, intentar crear OCOs (TP/SL) según la señal
            if is_valid and response is not None:
                try:
                    await self.position_manager.create_oco_orders(response, signal)
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo crear OCO tras entrada: {e}")

        except Exception as e:
            logger.error(f"❌ Error en _handle_buy: {e}")
            logger.error(f"📋 Traceback: {traceback.format_exc()}")

    async def _handle_sell(self, signal: SignalContract):
        """Maneja venta con señal validada"""
        try:
            rsi_value = signal.get('rsi')
            position_size = signal.get('position_size_usdt')
            reason = signal.get('reason', 'Sin razón')
            strategy_name = signal.get('strategy_name', 'Desconocida')

            rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "N/A"
            position_str = f"{position_size:.2f}" if position_size is not None else "N/A"

            logger.info(
                f"🔴 VENTA | {signal['symbol']} @ {signal['price']:.2f} | "
                f"RSI: {rsi_str} | Tamaño: {position_str} USDT | "
                f"Estrategia: {strategy_name} | Razón: {reason}"
            )

            self.order = await self.position_manager.build_market_order(signal=signal)

            if self.order is None:
                logger.warning("⚠️ No se pudo construir orden de venta")
                return

            logger.info(f"📦 Ejecutando orden: {self.order}")

            # Ejecutar orden
            if hasattr(self.rest_client, 'async_create_order'):
                response = await self.rest_client.async_create_order(
                    symbol=self.order['symbol'],
                    side=self.order['side'],
                    type_=self.order['type'],
                    quantity=self.order['quantity'],
                )
            else:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, self.rest_client.create_order,
                                                      self.order['symbol'], self.order['side'], self.order['type'], self.order['quantity'])

            # Validar respuesta
            if response is None:
                logger.error(f"❌ No se recibió respuesta del exchange")
                is_valid = False
            else:
                is_valid = is_valid_binance_response(response)
                if is_valid:
                    logger.info(f"✅ Orden ejecutada exitosamente")
                else:
                    logger.error(f"❌ Orden rechazada por Binance")

            # Persistir
            await self._persist_order_and_fills(
                request_payload={
                    "symbol": self.order['symbol'],
                    "side": self.order['side'],
                    "type": self.order['type'],
                    "quantity": self.order['quantity']
                },
                response=response,
                symbol=self.order['symbol'],
                side=self.order['side'],
                order_type=self.order['type'],
                quantity=self.order['quantity'],
            )

            # 🟠 Intentar crear OCO tras venta si corresponde
            if is_valid and response is not None:
                try:
                    await self.position_manager.create_oco_orders(response, signal)
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo crear OCO tras entrada: {e}")

        except Exception as e:
            logger.error(f"❌ Error en _handle_sell: {e}")
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
