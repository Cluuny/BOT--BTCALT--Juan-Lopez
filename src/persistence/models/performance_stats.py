from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from datetime import datetime
from persistence.db_connection import Base


class PerformanceStats(Base):
    __tablename__ = "performance_stats"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))

    period = Column(String(16), default="daily")  # daily/weekly/monthly
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)

    date = Column(DateTime, default=datetime.utcnow)
    pnl_total = Column(Float, default=0.0)
    gross_profit = Column(Float, default=0.0)
    gross_loss = Column(Float, default=0.0)
    fees_total = Column(Float, default=0.0)

    win_rate = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    sharpe = Column(Float, default=0.0)
    sortino = Column(Float, default=0.0)

    total_trades = Column(Integer, default=0)
    avg_trade = Column(Float, default=0.0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    best_trade = Column(Float, default=0.0)
    worst_trade = Column(Float, default=0.0)
    win_streak = Column(Integer, default=0)
    loss_streak = Column(Integer, default=0)
