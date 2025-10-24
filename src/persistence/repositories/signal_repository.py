from sqlalchemy.orm import Session
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
    ) -> Signal:
        signal = Signal(
            bot_id=bot_id,
            strategy_name=strategy_name,
            symbol=symbol,
            direction=direction,
            price=price,
            confidence=confidence,
            params_snapshot=params_snapshot,
            timestamp=datetime.utcnow(),
        )
        self.session.add(signal)
        self.session.commit()
        self.session.refresh(signal)
        return signal

    def get_latest_by_symbol(self, bot_id: int, symbol: str) -> Signal | None:
        return (
            self.session.query(Signal)
            .filter_by(bot_id=bot_id, symbol=symbol)
            .order_by(Signal.timestamp.desc())
            .first()
        )
