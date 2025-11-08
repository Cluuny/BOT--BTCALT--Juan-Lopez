import math

def test_build_with_position_size_usdt(position_manager, fake_rest_client):
    # Setup
    fake_rest_client.set_balance(1000.0)
    fake_rest_client.set_price(50000.0)  # precio simulado

    signal = {
        "symbol": "BTCUSDT",
        "type": "BUY",
        "price": 50000.0,
        "risk_params": {"position_size": 0.1},
        "position_size_usdt": 150.0,  # override absoluto
    }

    order = position_manager.build_market_order(signal)
    assert order is not None
    # cantidad esperada: 150 / 50000 = 0.003 => ajustada por stepSize 0.001 => 0.003
    expected_qty = 150.0 / 50000.0
    assert math.isclose(order["quantity"], expected_qty, rel_tol=1e-8)

def test_build_with_fractional_position_size(position_manager, fake_rest_client):
    fake_rest_client.set_balance(2000.0)
    fake_rest_client.set_price(40000.0)

    signal = {
        "symbol": "BTCUSDT",
        "type": "BUY",
        "price": 40000.0,
        "risk_params": {"position_size": 0.05},  # 5% del balance -> 100 USDT
    }

    order = position_manager.build_market_order(signal)
    assert order is not None
    expected_qty = (2000.0 * 0.05) / 40000.0
    assert abs(order["quantity"] - expected_qty) < 1e-8

def test_reject_below_min_notional(position_manager, fake_rest_client):
    # Balance pequeño para provocar que position_size_usdt < min_notional
    fake_rest_client.set_balance(5.0)  # muy bajo
    fake_rest_client.set_price(1000.0)

    signal = {
        "symbol": "BTCUSDT",
        "type": "BUY",
        "price": 1000.0,
        "risk_params": {"position_size": 0.5},
        # no position_size_usdt -> usará fracción sobre balance: 5 * 0.5 = 2.5 < min_notional (10)
    }

    order = position_manager.build_market_order(signal)
    assert order is None

