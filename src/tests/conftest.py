import sys
from pathlib import Path
import pytest
import time

# Asegurar que 'src' esté en sys.path para imports del proyecto
ROOT = Path(__file__).resolve().parents[1]  # apunta a .../src
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fixture: cliente REST falso y configurable
class FakeRestClient:
    def __init__(self, price=50000.0, usdt_balance=1000.0, min_notional=10.0, step_size=0.001, min_qty=0.001, max_qty=100.0):
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
    # pequeño sleep por si PositionManager hace operaciones inmediatas que dependan del tiempo
    time.sleep(0.001)
    return pm
