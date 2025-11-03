from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    run_id = Column(Integer, ForeignKey("bot_runs.id"), nullable=True)
    signal_uuid = Column(String(64), unique=True, nullable=True)

    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(20), index=True)
    direction = Column(String(10))  # buy / sell / close_long / close_short
    price = Column(Float)
    confidence = Column(Float, nullable=True)
    reason = Column(String(120), nullable=True)
    params_snapshot = Column(JSON, nullable=True)
    indicator_snapshot = Column(JSON, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    source_latency_ms = Column(Integer, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    bot = relationship("BotConfig", back_populates="signals")
    orders = relationship("Order", back_populates="signal")

    __table_args__ = (
        UniqueConstraint("signal_uuid", name="uq_signal_uuid"),
    )
