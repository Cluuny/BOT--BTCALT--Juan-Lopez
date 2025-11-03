from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from persistence.db_connection import Base


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    asset = Column(String(20), nullable=False)
    free = Column(Float, default=0.0)
    locked = Column(Float, default=0.0)
    total = Column(Float, default=0.0)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
