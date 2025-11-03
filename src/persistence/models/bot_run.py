from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class BotRun(Base):
    __tablename__ = "bot_runs"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=False)

    run_id = Column(String(64), unique=True, nullable=True)  # external correlation id
    mode = Column(String(20), default="TESTNET")
    env = Column(String(20), nullable=True)  # prod/dev
    git_commit = Column(String(64), nullable=True)

    status = Column(String(20), default="running")  # running/stopped/error
    reason = Column(String(255), nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Relationships (optional backrefs)
    bot = relationship("BotConfig")
