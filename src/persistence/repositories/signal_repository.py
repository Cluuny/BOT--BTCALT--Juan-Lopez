from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from persistence.models.signal import Signal


class SignalRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        bot_id: int,
        strategy_name: str,
        symbol: str,
        direction: str,
        price: float,
        confidence: float | None = None,
        params_snapshot: dict | None = None,
        run_id: int | None = None,
        signal_uuid: str | None = None,
        reason: str | None = None,
        indicator_snapshot: dict | None = None,
        valid_until: datetime | None = None,
        source_latency_ms: int | None = None,
    ) -> Signal:
        signal = Signal(
            bot_id=bot_id,
            run_id=run_id,
            signal_uuid=signal_uuid,
            strategy_name=strategy_name,
            symbol=symbol,
            direction=direction,
            price=price,
            confidence=confidence,
            reason=reason,
            params_snapshot=params_snapshot,
            indicator_snapshot=indicator_snapshot,
            valid_until=valid_until,
            source_latency_ms=source_latency_ms,
            timestamp=datetime.utcnow(),
        )
        try:
            self.session.add(signal)
            self.session.commit()
        except IntegrityError:
            # likely duplicate signal_uuid
            self.session.rollback()
            if signal_uuid:
                return self.get_by_uuid(signal_uuid)
            raise
        self.session.refresh(signal)
        return signal

    def get_by_uuid(self, signal_uuid: str) -> Signal | None:
        return self.session.query(Signal).filter_by(signal_uuid=signal_uuid).first()

    def get_latest_by_symbol(self, bot_id: int, symbol: str) -> Signal | None:
        return (
            self.session.query(Signal)
            .filter_by(bot_id=bot_id, symbol=symbol)
            .order_by(Signal.timestamp.desc())
            .first()
        )

    def list_between(self, bot_id: int, symbol: str | None, start: datetime, end: datetime):
        q = self.session.query(Signal).filter(
            Signal.bot_id == bot_id,
            Signal.timestamp >= start,
            Signal.timestamp <= end,
        )
        if symbol:
            q = q.filter(Signal.symbol == symbol)
        return q.order_by(Signal.timestamp.asc()).all()
