from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    order_id = Column(Integer, ForeignKey("orders.id"))
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    position_size = Column(Float)
    duration = Column(Float, nullable=True)
    timestamp_entry = Column(DateTime, default=datetime.utcnow)
    timestamp_exit = Column(DateTime, nullable=True)

    bot = relationship("BotConfig", back_populates="trades")
    order = relationship("Order", back_populates="trade")
