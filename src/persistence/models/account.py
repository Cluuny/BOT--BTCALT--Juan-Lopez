from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from datetime import datetime
from persistence.db_connection import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50))
    account_id = Column(String(100), unique=True)
    account_type = Column(String(20), default="SPOT")
    can_trade = Column(Boolean, default=True)

    balance_total = Column(Float, default=0.0)
    balance_available = Column(Float, default=0.0)
    margin_used = Column(Float, default=0.0)

    maker_commission = Column(Float, default=0.0)
    taker_commission = Column(Float, default=0.0)
    permissions = Column(JSON, nullable=True)

    last_synced_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
