from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from persistence.models.performance_stats import PerformanceStats


class PerformanceStatsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_or_update_period(
        self,
        bot_id: int,
        period: str,  # "daily" | "weekly" | "monthly" | custom
        start_at: datetime,
        end_at: datetime,
        **metrics,
    ) -> PerformanceStats:
        record = (
            self.session.query(PerformanceStats)
            .filter(
                PerformanceStats.bot_id == bot_id,
                PerformanceStats.period == period,
                PerformanceStats.start_at == start_at,
                PerformanceStats.end_at == end_at,
            )
            .first()
        )

        if record:
            for k, v in metrics.items():
                if hasattr(record, k) and v is not None:
                    setattr(record, k, v)
        else:
            record = PerformanceStats(
                bot_id=bot_id,
                period=period,
                start_at=start_at,
                end_at=end_at,
                date=end_at or datetime.utcnow(),
                **{k: v for k, v in metrics.items() if hasattr(PerformanceStats, k)},
            )
            self.session.add(record)

        self.session.commit()
        self.session.refresh(record)
        return record

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
        return self.create_or_update_period(
            bot_id=bot_id,
            period="daily",
            start_at=start_of_day,
            end_at=end_of_day,
            pnl_total=pnl_total,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            total_trades=total_trades,
        )

    def get_latest(self, bot_id: int) -> PerformanceStats | None:
        return (
            self.session.query(PerformanceStats)
            .filter_by(bot_id=bot_id)
            .order_by(PerformanceStats.date.desc())
            .first()
        )

    def list_between(self, bot_id: int, start: datetime, end: datetime):
        return (
            self.session.query(PerformanceStats)
            .filter(
                PerformanceStats.bot_id == bot_id,
                PerformanceStats.date >= start,
                PerformanceStats.date <= end,
            )
            .order_by(PerformanceStats.date.asc())
            .all()
        )
