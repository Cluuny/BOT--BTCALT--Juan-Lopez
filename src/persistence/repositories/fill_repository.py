from sqlalchemy.orm import Session
from typing import List, Optional
from persistence.models.fill import Fill


class FillRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(
        self,
        order_id: int,
        price: float,
        qty: float,
        quote_qty: Optional[float] = None,
        commission: Optional[float] = None,
        commission_asset: Optional[str] = None,
        is_maker: bool = False,
        trade_id: Optional[str] = None,
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

    def bulk_add(self, fills: List[dict]) -> List[Fill]:
        instances: List[Fill] = []
        for data in fills:
            instances.append(Fill(**data))
        self.session.add_all(instances)
        self.session.commit()
        return instances

    def list_by_order(self, order_id: int) -> List[Fill]:
        return self.session.query(Fill).filter_by(order_id=order_id).all()
