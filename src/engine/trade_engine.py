import asyncio
from utils.logger import Logger
from position.position_manager import PositionManager

from strategies.BaseStrategy import BaseStrategy
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.order_repository import OrderRepository
from persistence.repositories.fill_repository import FillRepository
from persistence.repositories.balance_snapshot_repository import BalanceSnapshotRepository
from persistence.repositories.signal_repository import SignalRepository
from persistence.repositories.log_repository import LogRepository
from persistence.repositories.account_repository import AccountRepository

logger = Logger.get_logger(__name__)


class TradeEngine:
    """
    Módulo que escucha las señales de trading y actúa en consecuencia.
    """

    def __init__(self, signal_queue: asyncio.Queue, bot_id: int, run_db_id: int | None = None):
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        self.rest_client = BinanceRESTClient(testnet=True)
        self.position_manager = PositionManager(rest_client=self.rest_client)
        self.order = None

    async def start(self):
        """Escucha continuamente la cola de señales."""
        while True:
            signal = await self.signal_queue.get()
            logger.info(f"📡 TradeEngine recibió señal: {signal}")

            # Aquí luego puedes conectar órdenes, gestión de riesgo, etc.
            await self.handle_signal(signal)

            self.signal_queue.task_done()

    async def handle_signal(self, signal):
        logger.info(f"🔔 Procesando señal: {signal}")
        if signal["type"] == "BUY":
            await self._handle_buy(signal=signal)
        else:
            await self._handle_sell(signal=signal)

    def _persist_order_and_fills(self, request_payload: dict, response: dict, symbol: str, side: str, order_type: str, quantity: float):
        session = db.get_session()
        try:
            order_repo = OrderRepository(session)
            fill_repo = FillRepository(session)
            balance_repo = BalanceSnapshotRepository(session)
            signal_repo = SignalRepository(session)
            log_repo = LogRepository(session)
            account_repo = AccountRepository(session)

            # Vincular la orden con la última señal del mismo símbolo (si existe)
            latest_signal = None
            try:
                latest_signal = signal_repo.get_latest_by_symbol(bot_id=self.bot_id, symbol=symbol)
            except Exception as e:
                logger.warning(f"No fue posible obtener la última señal para {symbol}: {e}")

            exchange_order_id = str(response.get("orderId")) if response.get("orderId") else ""
            status = response.get("status") or "NEW"
            time_in_force = response.get("timeInForce")

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
                client_order_id=response.get("clientOrderId"),
                time_in_force=time_in_force,
                request_payload=request_payload,
            )

            # Guardar payload completo y posibles errores
            order_repo.set_exchange_payload(order_id=order.id, exchange_response=response)
            try:
                log_repo.add_log(
                    bot_id=self.bot_id,
                    run_id=self.run_db_id,
                    level="INFO",
                    component="engine",
                    correlation_id=str(order.id),
                    message=f"Orden creada {symbol} {side} {order_type} qty={quantity} status={status}",
                    context={"request": request_payload, "response": response},
                )
            except Exception:
                pass

            # Fills de la respuesta (para MARKET usualmente presentes)
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

            # Actualizar cantidades ejecutadas y avg price si corresponde
            executed_qty = float(response.get("executedQty", total_qty)) if response else total_qty
            cummulative_quote_qty = float(response.get("cummulativeQuoteQty", total_quote)) if response else total_quote
            avg_price = (cummulative_quote_qty / executed_qty) if executed_qty else None
            order_repo.update_exec_quantities(
                order_id=order.id,
                executed_qty=executed_qty,
                cummulative_quote_qty=cummulative_quote_qty,
                avg_price=avg_price,
            )

            # Si la orden quedó en estado terminal, marcar is_working=False
            final_status = response.get("status") if response else None
            if final_status in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}:
                try:
                    order_repo.set_is_working(order_id=order.id, is_working=False)
                except Exception:
                    pass

            # Si la orden quedó completamente FILLED, tomar snapshot de cuenta y balances
            if final_status == "FILLED":
                try:
                    acct = self.rest_client.get_account_info()
                    # Resumen de cuenta
                    try:
                        account_id = acct.get("accountType") or "SPOT"
                        account_repo.create_or_update(
                            exchange="BINANCE",
                            account_id=account_id,
                            balance_total=0.0,  # no provisto por Binance, se puede calcular por assets si se desea
                            balance_available=0.0,
                            account_type=acct.get("accountType", "SPOT"),
                            can_trade=True,
                            maker_commission=float(acct.get("makerCommission", 0) or 0),
                            taker_commission=float(acct.get("takerCommission", 0) or 0),
                            permissions=acct.get("permissions"),
                        )
                    except Exception:
                        pass

                    # Snapshots por asset
                    balances = acct.get("balances", [])
                    for b in balances:
                        asset = b.get("asset")
                        free = float(b.get("free", 0) or 0)
                        locked = float(b.get("locked", 0) or 0)
                        balance_repo.add(bot_id=self.bot_id, asset=asset, free=free, locked=locked)

                    try:
                        log_repo.add_log(
                            bot_id=self.bot_id,
                            run_id=self.run_db_id,
                            level="INFO",
                            component="engine",
                            correlation_id=str(order.id),
                            message=f"BalanceSnapshot tomado post-FILLED para {symbol}",
                        )
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Error tomando BalanceSnapshot post-FILLED: {e}")
        finally:
            session.close()

    async def _handle_buy(self, signal):
        logger.info(
            f"🟢 Acción: ejecutar compra en {signal['symbol']} a {signal['price']} (RSI {signal['rsi']:.2f})"
        )
        self.order = self.position_manager.build_market_order(signal=signal)

        if self.order is None:
            logger.warning("⚠️ No se pudo construir la orden de compra.")
            return

        logger.info(f"Detalles de la orden: {self.order}")

        # Llamar a create_order desempaquetando el diccionario
        response = self.rest_client.create_order(
            symbol=self.order['symbol'],
            side=self.order['side'],
            type_=self.order['type'],
            quantity=self.order['quantity'],
        )
        logger.info(f"✅ Orden ejecutada: {response}")
        if response:
            self._persist_order_and_fills(
                request_payload={"symbol": self.order['symbol'], "side": self.order['side'], "type": self.order['type'], "quantity": self.order['quantity']},
                response=response,
                symbol=self.order['symbol'],
                side=self.order['side'],
                order_type=self.order['type'],
                quantity=self.order['quantity'],
            )

    async def _handle_sell(self, signal):
        logger.info(
            f"🔴 Acción: ejecutar venta en {signal['symbol']} a {signal['price']} (RSI {signal['rsi']:.2f})"
        )
        self.order = self.position_manager.build_market_order(signal=signal)

        if self.order is None:
            logger.warning("⚠️ No se pudo construir la orden de venta.")
            return

        logger.info(f"Detalles de la orden: {self.order}")

        # Llamar a create_order desempaquetando el diccionario
        response = self.rest_client.create_order(
            symbol=self.order['symbol'],
            side=self.order['side'],
            type_=self.order['type'],
            quantity=self.order['quantity'],
        )
        logger.info(f"✅ Orden ejecutada: {response}")
        if response:
            self._persist_order_and_fills(
                request_payload={"symbol": self.order['symbol'], "side": self.order['side'], "type": self.order['type'], "quantity": self.order['quantity']},
                response=response,
                symbol=self.order['symbol'],
                side=self.order['side'],
                order_type=self.order['type'],
                quantity=self.order['quantity'],
            )