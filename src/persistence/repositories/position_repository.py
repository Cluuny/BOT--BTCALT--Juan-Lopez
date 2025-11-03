from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from persistence.models.position import Position


class PositionRepository:
    def __init__(self, session: Session):
        self.session = session

    def open_position(
        self,
        bot_id: int,
        symbol: str,
        qty: float,
        avg_entry_price: float,
        run_id: Optional[int] = None,
        entry_reason: Optional[str] = None,
        open_order_id: Optional[int] = None,
    ) -> Position:
        pos = Position(
            bot_id=bot_id,
            run_id=run_id,
            symbol=symbol,
            qty=qty,
            avg_entry_price=avg_entry_price,
            entry_reason=entry_reason,
            open_order_id=open_order_id,
            status="open",
            opened_at=datetime.utcnow(),
        )
        self.session.add(pos)
        self.session.commit()
        self.session.refresh(pos)
        return pos

    def get_open_by_symbol(self, bot_id: int, symbol: str) -> Optional[Position]:
        return (
            self.session.query(Position)
            .filter(Position.bot_id == bot_id, Position.symbol == symbol, Position.status == "open")
            .first()
        )

    def update_qty_and_price(self, position_id: int, qty: float, avg_entry_price: Optional[float] = None) -> Optional[Position]:
        pos = self.session.query(Position).filter_by(id=position_id).first()
        if not pos:
            return None
        pos.qty = qty
        if avg_entry_price is not None:
            pos.avg_entry_price = avg_entry_price
        self.session.commit()
        self.session.refresh(pos)
        return pos

    def close_position(
        self,
        position_id: int,
        close_order_id: Optional[int] = None,
        exit_reason: Optional[str] = None,
        pnl_realized: Optional[float] = None,
        fees_total: Optional[float] = None,
    ) -> Optional[Position]:
        pos = self.session.query(Position).filter_by(id=position_id).first()
        if not pos:
            return None
        pos.status = "closed"
        pos.closed_at = datetime.utcnow()
        if close_order_id is not None:
            pos.close_order_id = close_order_id
        if exit_reason is not None:
            pos.exit_reason = exit_reason
        if pnl_realized is not None:
            pos.pnl_realized = pnl_realized
        if fees_total is not None:
            pos.fees_total = fees_total
        self.session.commit()
        self.session.refresh(pos)
        return pos

    def list_open(self, bot_id: int) -> List[Position]:
        return (
            self.session.query(Position)
            .filter(Position.bot_id == bot_id, Position.status == "open")
            .all()
        )
