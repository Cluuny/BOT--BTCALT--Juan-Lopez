from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from datetime import datetime
from persistence.db_connection import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=True)
    run_id = Column(Integer, ForeignKey("bot_runs.id"), nullable=True)
    level = Column(String(10), default="INFO")  # INFO / WARNING / ERROR
    component = Column(String(30), nullable=True)  # engine/strategy/data/rest
    correlation_id = Column(String(64), nullable=True)
    message = Column(String(1024))
    context = Column(JSON, nullable=True)
    extra = Column(JSON, nullable=True)
    stacktrace = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
