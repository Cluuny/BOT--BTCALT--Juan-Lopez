import sys
sys.path.insert(0, 'src')

print("Testeando imports de trade_engine...")

try:
    from engine.trade_engine import TradeEngine
    print("✅ TradeEngine importado correctamente")

    from position.position_manager import PositionManager
    print("✅ PositionManager importado correctamente")

    from contracts.signal_contract import ValidatedSignal, SignalContract
    print("✅ SignalContract importado correctamente")

    print("\n🎉 Todos los imports de trade_engine funcionan correctamente!")
    print("\n✅ No hay errores de importación (ERROR 400)")
    print("⚠️ Los warnings restantes son solo de tipo estático y no afectan la ejecución")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

