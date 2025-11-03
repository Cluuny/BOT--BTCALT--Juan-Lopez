from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from persistence.db_connection import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bot_configs.id"))
    run_id = Column(Integer, ForeignKey("bot_runs.id"), nullable=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)

    client_order_id = Column(String(64), unique=True, nullable=True)
    exchange_order_id = Column(String(100), index=True)

    symbol = Column(String(20))
    side = Column(String(10))  # buy / sell
    type = Column(String(20))  # market / limit / stop
    time_in_force = Column(String(10), nullable=True)  # GTC / IOC / FOK

    status = Column(String(20), default="NEW")  # Binance-aligned
    is_working = Column(Boolean, default=True)

    # Prices and quantities
    price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)

    orig_qty = Column(Float, nullable=True)
    executed_qty = Column(Float, nullable=True)
    cummulative_quote_qty = Column(Float, nullable=True)
    iceberg_qty = Column(Float, nullable=True)

    # Backward-compat fields
    quantity = Column(Float, nullable=True)

    # Timestamps
    transact_time = Column(DateTime, nullable=True)
    last_exchange_update_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Raw payloads and errors
    request_payload = Column(JSON, nullable=True)
    exchange_response = Column(JSON, nullable=True)
    last_error = Column(String(255), nullable=True)

    # Relations and grouping
    oco_group_id = Column(String(64), nullable=True)
    dup_of_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    bot = relationship("BotConfig", back_populates="orders")
    signal = relationship("Signal", back_populates="orders")
    trade = relationship("Trade", back_populates="order", uselist=False)
    fills = relationship("Fill", back_populates="order")

    __table_args__ = (
        UniqueConstraint("client_order_id", name="uq_client_order_id"),
    )
