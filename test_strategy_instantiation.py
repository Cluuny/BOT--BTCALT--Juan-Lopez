import sys
sys.path.insert(0, 'src')
import asyncio

print("Testeando instanciación de estrategias con parámetros...")

try:
    from strategies.live_strategies.DownALTBuyer import DownALTBuyer
    from strategies.live_strategies.OpenDownBuyStrategy import OpenDownBuyStrategy
    from strategies.live_strategies.bbands_rsi_mean_reversion import BBANDS_RSI_MeanReversionStrategy
    from strategies.live_strategies.btc_rsi import BTC_RSI_Strategy
    from strategies.examples.simple_mean_reversion import SimpleMeanReversionStrategy

    # Crear queue de prueba
    signal_queue = asyncio.Queue()

    print("\n1️⃣ Testeando DownALTBuyer con parámetros personalizados...")
    strategy1 = DownALTBuyer(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        entry_threshold=-1.0,
        exit_threshold=2.0,
        position_size_percent=100.0,
        base_capital=10.0,
        timeframe="1m"
    )
    print(f"   ✅ DownALTBuyer instanciado correctamente")
    print(f"      - position_size_percent: {strategy1.position_size_percent}")
    print(f"      - base_capital: {strategy1.base_capital}")

    print("\n2️⃣ Testeando OpenDownBuyStrategy con parámetros personalizados...")
    strategy2 = OpenDownBuyStrategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT"],
        entry_threshold=-1.0,
        exit_threshold=2.0,
        position_size_percent=100.0,
        base_capital=10.0,
        timeframe="1m"
    )
    print(f"   ✅ OpenDownBuyStrategy instanciado correctamente")
    print(f"      - position_size_percent: {strategy2.position_size_percent}")
    print(f"      - base_capital: {strategy2.base_capital}")

    print("\n3️⃣ Testeando BBANDS_RSI_MeanReversionStrategy...")
    strategy3 = BBANDS_RSI_MeanReversionStrategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        bb_period=20,
        bb_std=2.0,
        rsi_period=14,
        rsi_buy_threshold=40.0,
        rsi_sell_threshold=60.0,
        sma_period=50,
        vol_sma_period=20,
        enforce_volume_filter=True,
        max_holding_hours=48,
        timeframe="1m"
    )
    print(f"   ✅ BBANDS_RSI_MeanReversionStrategy instanciado correctamente")

    print("\n4️⃣ Testeando BTC_RSI_Strategy...")
    strategy4 = BTC_RSI_Strategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        rsi_period=14,
        overbought=70,
        oversold=30,
        timeframe="1m"
    )
    print(f"   ✅ BTC_RSI_Strategy instanciado correctamente")

    print("\n5️⃣ Testeando SimpleMeanReversionStrategy...")
    strategy5 = SimpleMeanReversionStrategy(
        signal_queue=signal_queue,
        bot_id=1,
        symbols=["BTCUSDT", "ETHUSDT"],
        period=20,
        std=2.0,
        max_holding_hours=48,
        timeframe="1m"
    )
    print(f"   ✅ SimpleMeanReversionStrategy instanciado correctamente")

    print("\n" + "="*60)
    print("🎉 TODAS LAS ESTRATEGIAS SE INSTANCIAN CORRECTAMENTE")
    print("="*60)
    print("\n✅ Error TypeError resuelto:")
    print("   'EnhancedBaseStrategy.__init__() got an unexpected keyword argument'")
    print("\n✅ Todas las estrategias filtran kwargs correctamente")
    print("✅ Los parámetros personalizados se pasan sin problemas")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

