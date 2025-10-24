from sqlalchemy.orm import Session
from datetime import datetime
from persistence.models.trade import Trade


class TradeRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        bot_id: int,
        order_id: int,
        entry_price: float,
        position_size: float,
        timestamp_entry: datetime | None = None,
    ) -> Trade:
        trade = Trade(
            bot_id=bot_id,
            order_id=order_id,
            entry_price=entry_price,
            position_size=position_size,
            timestamp_entry=timestamp_entry or datetime.utcnow(),
        )
        self.session.add(trade)
        self.session.commit()
        self.session.refresh(trade)
        return trade

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_percent: float | None = None,
    ):
        trade = self.session.query(Trade).filter_by(id=trade_id).first()
        if trade:
            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.pnl_percent = pnl_percent
            trade.timestamp_exit = datetime.utcnow()
            trade.duration = (
                trade.timestamp_exit - trade.timestamp_entry
            ).total_seconds()
            self.session.commit()
        return trade

    def get_open_trades(self, bot_id: int):
        return self.session.query(Trade).filter_by(bot_id=bot_id, exit_price=None).all()
