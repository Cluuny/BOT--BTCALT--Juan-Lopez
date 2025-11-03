from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Fill(Base):
    __tablename__ = "fills"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    trade_id = Column(String(100), index=True)  # Binance trade id
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    quote_qty = Column(Float, nullable=True)
    commission = Column(Float, nullable=True)
    commission_asset = Column(String(20), nullable=True)
    is_maker = Column(Boolean, default=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="fills")
