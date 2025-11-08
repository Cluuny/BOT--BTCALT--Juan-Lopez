import pytest
from contracts.signal_contract import ValidatedSignal

def test_valid_signal_with_position_size_usdt():
    raw = {
        "symbol": "BTCUSDT",
        "type": "BUY",
        "price": 50000,
        "risk_params": {"position_size": 0.1},
        "position_size_usdt": 100,
        "strategy_name": "DailyOpen"
    }
    sig = ValidatedSignal.validate(raw)
    assert sig["price"] == 50000.0
    assert sig["position_size_usdt"] == 100.0
    assert "received_at" in sig

def test_valid_signal_with_fractional_position_size():
    raw = {
        "symbol": "BTCUSDT",
        "type": "SELL",
        "price": 42000.5,
        "risk_params": {"position_size": 0.02},
        "strategy_name": "EMA"
    }
    sig = ValidatedSignal.validate(raw)
    assert sig["price"] == 42000.5
    # position_size debe haberse normalizado dentro de risk_params (dict)
    assert isinstance(sig["risk_params"], dict)
    assert 0 < sig["risk_params"]["position_size"] <= 1

def test_invalid_signal_missing_fields():
    raw = {"symbol": "BTCUSDT", "type": "BUY"}
    with pytest.raises(ValueError):
        ValidatedSignal.validate(raw)

