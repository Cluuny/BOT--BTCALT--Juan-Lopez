import os
import pytest

try:
    from binance import Client
except Exception:
    Client = None

from config.settings import settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope='session')
def integration_enabled():
    # Only run integration tests when explicitly allowed
    run_integration = os.getenv('RUN_INTEGRATION', 'false').lower() in ('1', 'true', 'yes')
    if not run_integration:
        pytest.skip('Integration tests disabled. Set RUN_INTEGRATION=true to enable.')

    if settings.MODE != 'TESTNET':
        pytest.skip('Integration tests require settings.MODE=TESTNET')

    if not settings.API_KEY or not settings.API_SECRET:
        pytest.skip('Missing API credentials in environment for integration tests')

    if Client is None:
        pytest.skip('python-binance client not installed')

    return True


def test_binance_ping_and_time(integration_enabled):
    # minimal sanity check against Binance testnet
    client = Client(settings.API_KEY, settings.API_SECRET, testnet=True)
    pong = client.ping()
    assert isinstance(pong, dict) or pong is None
    servertime = client.get_server_time()
    assert 'serverTime' in servertime

