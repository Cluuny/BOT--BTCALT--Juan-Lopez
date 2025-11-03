from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from persistence.db_connection import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("bot_runs.id"), nullable=True)

    symbol = Column(String(20), nullable=False)
    side = Column(String(10), default="LONG")  # Spot is typically LONG

    qty = Column(Float, default=0.0)  # net quantity
    avg_entry_price = Column(Float, default=0.0)

    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    status = Column(String(10), default="open")  # open/closed

    pnl_realized = Column(Float, default=0.0)
    pnl_unrealized = Column(Float, default=0.0)
    fees_total = Column(Float, default=0.0)

    max_favorable_excursion = Column(Float, default=0.0)
    max_adverse_excursion = Column(Float, default=0.0)

    entry_reason = Column(String(120), nullable=True)
    exit_reason = Column(String(120), nullable=True)

    open_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    close_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
