from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from persistence.models.balance_snapshot import BalanceSnapshot


class BalanceSnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, bot_id: Optional[int], asset: str, free: float, locked: float, account_id: Optional[int] = None, timestamp: Optional[datetime] = None) -> BalanceSnapshot:
        snap = BalanceSnapshot(
            bot_id=bot_id,
            account_id=account_id,
            asset=asset,
            free=free,
            locked=locked,
            total=(free or 0.0) + (locked or 0.0),
            timestamp=timestamp or datetime.utcnow(),
        )
        self.session.add(snap)
        self.session.commit()
        self.session.refresh(snap)
        return snap

    def bulk_add(self, snapshots: List[dict]) -> List[BalanceSnapshot]:
        instances: List[BalanceSnapshot] = [BalanceSnapshot(**d) for d in snapshots]
        self.session.add_all(instances)
        self.session.commit()
        return instances

    def list_by_bot(self, bot_id: int, asset: Optional[str] = None, limit: int = 100) -> List[BalanceSnapshot]:
        q = self.session.query(BalanceSnapshot).filter(BalanceSnapshot.bot_id == bot_id)
        if asset:
            q = q.filter(BalanceSnapshot.asset == asset)
        return q.order_by(BalanceSnapshot.timestamp.desc()).limit(limit).all()
