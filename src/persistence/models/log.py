from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from datetime import datetime
from persistence.db_connection import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"), nullable=True)
    level = Column(String(10), default="INFO")  # INFO / WARNING / ERROR
    message = Column(String(255))
    context = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
