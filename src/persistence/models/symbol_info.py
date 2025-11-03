from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
from datetime import datetime
from persistence.db_connection import Base


class SymbolInfo(Base):
    __tablename__ = "symbol_info"

    symbol = Column(String(20), primary_key=True)
    base_asset = Column(String(20), nullable=True)
    quote_asset = Column(String(20), nullable=True)
    status = Column(String(20), nullable=True)

    minQty = Column(Float, nullable=True)
    stepSize = Column(Float, nullable=True)
    minNotional = Column(Float, nullable=True)
    tickSize = Column(Float, nullable=True)

    quotePrecision = Column(Integer, nullable=True)
    baseAssetPrecision = Column(Integer, nullable=True)

    filters = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
