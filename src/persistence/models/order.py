from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    exchange_order_id = Column(String(100), index=True)
    symbol = Column(String(20))
    side = Column(String(10))  # buy / sell
    type = Column(String(20))  # market / limit / stop
    status = Column(String(20), default="new")  # new / filled / cancelled / rejected
    price = Column(Float)
    quantity = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bot = relationship("BotConfig", back_populates="orders")
    signal = relationship("Signal", back_populates="orders")
    trade = relationship("Trade", back_populates="order", uselist=False)
