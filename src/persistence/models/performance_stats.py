from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from datetime import datetime
from persistence.db_connection import Base


class PerformanceStats(Base):
    __tablename__ = "performance_stats"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    date = Column(DateTime, default=datetime.utcnow)
    pnl_total = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
