from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from persistence.db_connection import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50))
    account_id = Column(String(100), unique=True)
    balance_total = Column(Float, default=0.0)
    balance_available = Column(Float, default=0.0)
    margin_used = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
