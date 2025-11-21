import sys
sys.path.insert(0, 'src')
import asyncio

print("Testeando emisión de señales con position_size_usdt...")

async def test_signal_emission():
    try:
        from strategies.core.signal_emitter import SignalEmitter

        # Crear queue y emitter
        signal_queue = asyncio.Queue()
        emitter = SignalEmitter(signal_queue=signal_queue, bot_id=1, run_db_id=1)

        print("\n1️⃣ Testeando señal BUY con position_size_usdt en metadata...")

        # Emitir señal con position_size_usdt en metadata (como lo hace OpenDownBuyStrategy)
        await emitter.emit_buy(
            symbol="BTCUSDT",
            price=84091.69,
            reason="Test de señal",
            indicator_snapshot={'close': 84091.69, 'volume': 45.71},
            metadata={
                'strategy': 'OpenDownBuy',
                'position_size_usdt': 10.0,  # ⚠️ IMPORTANTE: En metadata
                'change_pct': -2.94,
            }
        )

        # Obtener señal de la queue
        signal = await asyncio.wait_for(signal_queue.get(), timeout=1.0)

        print("\n✅ Señal emitida y recibida")
        print(f"\n📋 Estructura de la señal:")
        print(f"   - symbol: {signal.get('symbol')}")
        print(f"   - type: {signal.get('type')}")
        print(f"   - price: {signal.get('price')}")
        print(f"   - position_size_usdt (nivel superior): {signal.get('position_size_usdt')}")
        print(f"   - risk_params: {signal.get('risk_params')}")
        print(f"   - metadata: {signal.get('metadata')}")

        # Verificar que position_size_usdt esté en el nivel superior
        if 'position_size_usdt' in signal:
            print("\n✅ ¡CORRECTO! position_size_usdt está en el nivel superior")
            print(f"   Valor: {signal['position_size_usdt']} USDT")
        else:
            print("\n❌ ERROR: position_size_usdt NO está en el nivel superior")
            return False

        # Verificar que risk_params no esté vacío
        if signal.get('risk_params') and signal['risk_params'] != {}:
            print(f"✅ risk_params tiene contenido: {signal['risk_params']}")
        else:
            print(f"⚠️  risk_params está presente pero puede estar vacío: {signal['risk_params']}")

        print("\n2️⃣ Testeando validación de la señal...")
        from contracts.signal_contract import ValidatedSignal

        try:
            validated = ValidatedSignal.validate(signal)
            print("✅ Señal validada correctamente por SignalContract")
            print(f"   - symbol: {validated['symbol']}")
            print(f"   - type: {validated['type']}")
            print(f"   - position_size_usdt: {validated.get('position_size_usdt', 'N/A')}")
            return True
        except Exception as e:
            print(f"❌ Señal rechazada por validador: {e}")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Ejecutar test
result = asyncio.run(test_signal_emission())

if result:
    print("\n" + "="*60)
    print("🎉 TEST EXITOSO")
    print("="*60)
    print("\n✅ La señal se emite correctamente")
    print("✅ position_size_usdt está en el nivel superior")
    print("✅ El validador acepta la señal")
    print("\n💡 El error del log está RESUELTO")
else:
    print("\n" + "="*60)
    print("❌ TEST FALLIDO")
    print("="*60)
    sys.exit(1)

