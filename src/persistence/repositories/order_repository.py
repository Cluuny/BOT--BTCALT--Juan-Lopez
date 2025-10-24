from sqlalchemy.orm import Session
from datetime import datetime
from persistence.models.order import Order


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
        price: float,
        quantity: float,
        status: str = "new",
    ) -> Order:
        order = Order(
            bot_id=bot_id,
            signal_id=signal_id,
            exchange_order_id=exchange_order_id,
            symbol=symbol,
            side=side,
            type=type,
            price=price,
            quantity=quantity,
            status=status,
            created_at=datetime.utcnow(),
        )
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        return order

    def update_status(self, exchange_order_id: str, status: str) -> Order | None:
        order = (
            self.session.query(Order)
            .filter_by(exchange_order_id=exchange_order_id)
            .first()
        )
        if order:
            order.status = status
            order.updated_at = datetime.utcnow()
            self.session.commit()
        return order

    def get_open_orders(self, bot_id: int):
        return self.session.query(Order).filter_by(bot_id=bot_id, status="open").all()
