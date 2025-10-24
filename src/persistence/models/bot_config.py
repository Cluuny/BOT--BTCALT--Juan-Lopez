from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class BotConfig(Base):
    __tablename__ = "bot_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    mode = Column(String(20), default="TESTNET")  # TESTNET / REAL
    exchange = Column(String(50), nullable=False)
    status = Column(String(20), default="stopped")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    signals = relationship("Signal", back_populates="bot")
    orders = relationship("Order", back_populates="bot")
    trades = relationship("Trade", back_populates="bot")

    __table_args__ = (
        UniqueConstraint("name", "exchange", name="uq_bot_name_exchange"),
    )
