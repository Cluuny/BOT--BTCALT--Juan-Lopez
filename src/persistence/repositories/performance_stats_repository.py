from sqlalchemy import DateTime
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from persistence.models.performance_stats import PerformanceStats


class PerformanceStatsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_or_update_daily(
        self,
        bot_id: int,
        pnl_total: float,
        win_rate: float,
        max_drawdown: float,
        profit_factor: float,
        total_trades: int,
    ) -> PerformanceStats:
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)

        record = (
            self.session.query(PerformanceStats)
            .filter(
                PerformanceStats.bot_id == bot_id,
                PerformanceStats.date >= start_of_day,
                PerformanceStats.date < end_of_day,
            )
            .first()
        )

        if record:
            record.pnl_total = pnl_total
            record.win_rate = win_rate
            record.max_drawdown = max_drawdown
            record.profit_factor = profit_factor
            record.total_trades = total_trades
        else:
            record = PerformanceStats(
                bot_id=bot_id,
                date=datetime.utcnow(),
                pnl_total=pnl_total,
                win_rate=win_rate,
                max_drawdown=max_drawdown,
                profit_factor=profit_factor,
                total_trades=total_trades,
            )
            self.session.add(record)

        self.session.commit()
        self.session.refresh(record)
        return record

    def get_latest(self, bot_id: int) -> PerformanceStats | None:
        return (
            self.session.query(PerformanceStats)
            .filter_by(bot_id=bot_id)
            .order_by(PerformanceStats.date.desc())
            .first()
        )
