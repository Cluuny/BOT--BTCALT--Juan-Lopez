# conftest.py
# Añade la carpeta `src` al PYTHONPATH para que las importaciones como
# `persistence`, `utils`, `data`, etc. (que viven en src/) funcionen
# durante la ejecución de pytest.
import sys
import os
ROOT = os.path.dirname(__file__)
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pytest
from pathlib import Path

# Configurar pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# --- Fixture DB de prueba (SQLite in-memory) ---
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from persistence import models as persistence_models
from persistence.db_connection import Base, load_models

_engine = create_engine("sqlite:///:memory:")
# Cargar modelos del paquete persistence.models
load_models(persistence_models)
Base.metadata.create_all(_engine)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

class DBTest:
    def get_session(self):
        return _SessionLocal()

@pytest.fixture(scope="session")
def db():
    return DBTest()

# --- Fixtures para PositionManager tests (mantener fake client simple) ---
class FakeRestClient:
    def __init__(self, price=50000.0, usdt_balance=1000.0, min_notional=10.0, step_size=0.0001, min_qty=0.0001, max_qty=100.0):
        self._price = float(price)
        self._usdt_balance = float(usdt_balance)
        self._min_notional = float(min_notional)
        self._step_size = float(step_size)
        self._min_qty = float(min_qty)
        self._max_qty = float(max_qty)
        self._open_orders = []

    def get_symbol_price(self, symbol: str) -> float:
        return self._price

    def get_USDT_balance(self):
        # Retornar estructura simple similar a cliente real
        return {"asset": "USDT", "free": str(self._usdt_balance), "locked": "0"}

    def get_exchange_info(self):
        # Estructura simplificada con filtros necesarios por PositionManager
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "filters": [
                        {"filterType": "MIN_NOTIONAL", "minNotional": str(self._min_notional)},
                        {"filterType": "LOT_SIZE", "minQty": str(self._min_qty), "maxQty": str(self._max_qty), "stepSize": str(self._step_size)},
                    ],
                }
            ]
        }

    def get_open_orders(self, symbol: str = None):
        return list(self._open_orders)

    # métodos auxiliares para tests
    def set_price(self, p: float):
        self._price = float(p)

    def set_balance(self, b: float):
        self._usdt_balance = float(b)

@pytest.fixture
def fake_rest_client():
    return FakeRestClient()

@pytest.fixture
def position_manager(fake_rest_client):
    from position.position_manager import PositionManager
    pm = PositionManager(rest_client=fake_rest_client)
    return pm
