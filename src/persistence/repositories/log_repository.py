from sqlalchemy.orm import Session
from datetime import datetime
from persistence.models.log import Log


class LogRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_log(
        self, bot_id: int | None, level: str, message: str, context: dict | None = None
    ):
        log = Log(
            bot_id=bot_id,
            level=level,
            message=message,
            context=context,
            timestamp=datetime.utcnow(),
        )
        self.session.add(log)
        self.session.commit()
        return log

    def get_logs_by_bot(self, bot_id: int, limit: int = 50):
        return (
            self.session.query(Log)
            .filter_by(bot_id=bot_id)
            .order_by(Log.timestamp.desc())
            .limit(limit)
            .all()
        )
