from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(20), index=True)
    direction = Column(String(10))  # buy / sell / close_long / close_short
    price = Column(Float)
    confidence = Column(Float, nullable=True)
    params_snapshot = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    bot = relationship("BotConfig", back_populates="signals")
    orders = relationship("Order", back_populates="signal")
