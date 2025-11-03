from sqlalchemy.orm import Session
from datetime import datetime
from persistence.models.order import Order
from persistence.models.fill import Fill


class OrderRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        bot_id: int,
        signal_id: int | None,
        exchange_order_id: str,
        symbol: str,
        side: str,
        type: str,
        price: float | None = None,
        quantity: float | None = None,
        status: str = "NEW",
        run_id: int | None = None,
        client_order_id: str | None = None,
        time_in_force: str | None = None,
        request_payload: dict | None = None,
    ) -> Order:
        order = Order(
            bot_id=bot_id,
            run_id=run_id,
            signal_id=signal_id,
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            side=side,
            type=type,
            time_in_force=time_in_force,
            price=price,
            quantity=quantity,
            status=status,
            request_payload=request_payload,
            created_at=datetime.utcnow(),
        )
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        return order

    def set_is_working(self, order_id: int, is_working: bool) -> Order | None:
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None
        order.is_working = is_working
        order.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(order)
        return order

    def get_by_exchange_id(self, exchange_order_id: str) -> Order | None:
        return (
            self.session.query(Order)
            .filter_by(exchange_order_id=exchange_order_id)
            .first()
        )

    def get_by_client_id(self, client_order_id: str) -> Order | None:
        return self.session.query(Order).filter_by(client_order_id=client_order_id).first()

    def update_status(self, exchange_order_id: str, status: str) -> Order | None:
        order = self.get_by_exchange_id(exchange_order_id)
        if order:
            order.status = status
            order.updated_at = datetime.utcnow()
            self.session.commit()
        return order

    def set_exchange_payload(self, order_id: int, exchange_response: dict | None, last_error: str | None = None):
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None
        order.exchange_response = exchange_response
        if last_error:
            order.last_error = last_error
        order.updated_at = datetime.utcnow()
        self.session.commit()
        return order

    def update_exec_quantities(
        self,
        order_id: int,
        executed_qty: float | None = None,
        cummulative_quote_qty: float | None = None,
        avg_price: float | None = None,
        last_exchange_update_at: datetime | None = None,
    ) -> Order | None:
        order = self.session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None
        if executed_qty is not None:
            order.executed_qty = executed_qty
        if cummulative_quote_qty is not None:
            order.cummulative_quote_qty = cummulative_quote_qty
        if avg_price is not None:
            order.avg_price = avg_price
        if last_exchange_update_at is not None:
            order.last_exchange_update_at = last_exchange_update_at
        order.updated_at = datetime.utcnow()
        self.session.commit()
        return order

    def add_fill(
        self,
        order_id: int,
        price: float,
        qty: float,
        quote_qty: float | None = None,
        commission: float | None = None,
        commission_asset: str | None = None,
        is_maker: bool = False,
        trade_id: str | None = None,
    ) -> Fill:
        fill = Fill(
            order_id=order_id,
            trade_id=trade_id,
            price=price,
            qty=qty,
            quote_qty=quote_qty,
            commission=commission,
            commission_asset=commission_asset,
            is_maker=is_maker,
        )
        self.session.add(fill)
        self.session.commit()
        self.session.refresh(fill)
        return fill

    def get_open_orders(self, bot_id: int):
        # Binance open statuses typically NEW or PARTIALLY_FILLED and is_working true
        return (
            self.session.query(Order)
            .filter(Order.bot_id == bot_id, Order.is_working == True)
            .all()
        )
