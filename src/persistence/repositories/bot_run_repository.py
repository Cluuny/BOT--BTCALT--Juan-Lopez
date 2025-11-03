from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from persistence.models.bot_run import BotRun


class BotRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def start(
        self,
        bot_id: int,
        mode: str = "TESTNET",
        env: Optional[str] = None,
        run_id: Optional[str] = None,
        git_commit: Optional[str] = None,
    ) -> BotRun:
        run = BotRun(
            bot_id=bot_id,
            mode=mode,
            env=env,
            run_id=run_id,
            git_commit=git_commit,
            status="running",
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def end(self, run_db_id: int, status: str = "stopped", reason: Optional[str] = None) -> BotRun | None:
        run = self.session.query(BotRun).filter_by(id=run_db_id).first()
        if not run:
            return None
        run.status = status
        run.reason = reason
        run.ended_at = datetime.utcnow()
        self.session.commit()
        return run

    def get_by_run_id(self, run_id: str) -> BotRun | None:
        return self.session.query(BotRun).filter_by(run_id=run_id).first()
