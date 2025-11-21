"""
Tests para verificar que las estrategias migradas funcionan correctamente.
"""

import pytest
import asyncio
from strategies.live_strategies import (
    BBANDS_RSI_MeanReversionStrategy,
    BTC_RSI_Strategy,
    OpenDownBuyStrategy,
    DownALTBuyer
)


@pytest.mark.asyncio
async def test_bbands_rsi_strategy_initialization():
    """Verifica que BBANDS_RSI_MeanReversionStrategy se inicializa correctamente."""
    signal_queue = asyncio.Queue()

    strategy = BBANDS_RSI_MeanReversionStrategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT"],
        timeframe="1m",
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
    )

    assert strategy is not None
    assert strategy.symbols == ["BTCUSDT"]
    assert strategy.bb_period == 20
    assert strategy.rsi_period == 14
    assert len(strategy.indicators.indicators) == 0  # Aún no configurados

    # Configurar indicadores
    strategy.setup_indicators()
    assert len(strategy.indicators.indicators) > 0

    # Verificar nombres de indicadores
    indicator_names = strategy.indicators.get_indicator_names()
    assert 'RSI' in indicator_names
    assert 'BBL' in indicator_names or 'BBANDS' in indicator_names
    assert 'SMA50' in indicator_names


@pytest.mark.asyncio
async def test_btc_rsi_strategy_initialization():
    """Verifica que BTC_RSI_Strategy se inicializa correctamente."""
    signal_queue = asyncio.Queue()

    strategy = BTC_RSI_Strategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframe="1m",
        rsi_period=14,
        overbought=70,
        oversold=30,
    )

    assert strategy is not None
    assert strategy.symbols == ["BTCUSDT", "ETHUSDT"]
    assert strategy.rsi_period == 14
    assert strategy.overbought == 70
    assert strategy.oversold == 30

    # Configurar indicadores
    strategy.setup_indicators()
    indicator_names = strategy.indicators.get_indicator_names()
    assert 'RSI' in indicator_names


@pytest.mark.asyncio
async def test_open_down_buy_strategy_initialization():
    """Verifica que OpenDownBuyStrategy se inicializa correctamente."""
    signal_queue = asyncio.Queue()

    strategy = OpenDownBuyStrategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT"],
        timeframe="1m",
        entry_threshold=-1.0,
        exit_threshold=2.0,
        base_capital=10.0,
    )

    assert strategy is not None
    assert strategy.symbols == ["BTCUSDT"]
    assert strategy.symbol == "BTCUSDT"
    assert strategy.entry_threshold == -1.0
    assert strategy.exit_threshold == 2.0
    assert strategy.base_capital == 10.0
    assert strategy.position_open is False


@pytest.mark.asyncio
async def test_down_alt_buyer_strategy_initialization():
    """Verifica que DownALTBuyer se inicializa correctamente."""
    signal_queue = asyncio.Queue()

    strategy = DownALTBuyer(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframe="1m",
        entry_threshold=-1.0,
        exit_threshold=2.0,
    )

    assert strategy is not None
    assert "BTCUSDT" in strategy.symbols
    assert "ETHUSDT" in strategy.symbols


@pytest.mark.asyncio
async def test_all_strategies_have_required_methods():
    """Verifica que todas las estrategias tienen los métodos requeridos."""
    signal_queue = asyncio.Queue()

    strategies = [
        BBANDS_RSI_MeanReversionStrategy(
            signal_queue=signal_queue,
            bot_id=1,
            symbols=["BTCUSDT"],
        ),
        BTC_RSI_Strategy(
            signal_queue=signal_queue,
            bot_id=1,
            symbols=["BTCUSDT"],
        ),
        OpenDownBuyStrategy(
            signal_queue=signal_queue,
            bot_id=1,
            symbols=["BTCUSDT"],
        ),
        DownALTBuyer(
            signal_queue=signal_queue,
            bot_id=1,
            symbols=["BTCUSDT"],
        ),
    ]

    for strategy in strategies:
        # Verificar métodos abstractos implementados
        assert hasattr(strategy, 'setup_indicators')
        assert hasattr(strategy, 'check_conditions')
        assert callable(strategy.setup_indicators)
        assert callable(strategy.check_conditions)

        # Verificar métodos del framework
        assert hasattr(strategy, 'start')
        assert hasattr(strategy, 'emit_buy')
        assert hasattr(strategy, 'emit_sell')
        assert callable(strategy.start)
        assert callable(strategy.emit_buy)
        assert callable(strategy.emit_sell)


def test_strategy_imports():
    """Verifica que todas las estrategias se pueden importar."""
    from strategies.live_strategies import (
        BBANDS_RSI_MeanReversionStrategy,
        BTC_RSI_Strategy,
        OpenDownBuyStrategy,
        DownALTBuyer
    )

    assert BBANDS_RSI_MeanReversionStrategy is not None
    assert BTC_RSI_Strategy is not None
    assert OpenDownBuyStrategy is not None
    assert DownALTBuyer is not None


@pytest.mark.asyncio
async def test_indicator_calculation():
    """Verifica que el cálculo de indicadores funciona."""
    import pandas as pd
    from strategies.core.indicator_calculator import IndicatorCalculator

    # Crear datos de prueba
    data = {
        'open': [100, 101, 102, 103, 104] * 20,
        'high': [101, 102, 103, 104, 105] * 20,
        'low': [99, 100, 101, 102, 103] * 20,
        'close': [100.5, 101.5, 102.5, 103.5, 104.5] * 20,
        'volume': [1000, 1100, 1200, 1300, 1400] * 20,
    }
    df = pd.DataFrame(data)

    # Configurar calculadora
    calc = IndicatorCalculator()
    calc.add_rsi(14)
    calc.add_sma(20)
    calc.add_bbands(20, 2.0)

    # Calcular
    result = calc.compute(df)

    # Verificar que se calcularon
    assert 'RSI' in result.columns
    assert 'SMA20' in result.columns
    assert 'BBL' in result.columns or any('BB' in col for col in result.columns)

    # Verificar que hay valores (al menos en las últimas filas)
    assert result['RSI'].notna().sum() > 0
    assert result['SMA20'].notna().sum() > 0


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v", "-s"])

