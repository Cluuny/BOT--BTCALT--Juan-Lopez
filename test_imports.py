#!/usr/bin/env python
"""Test de importación para verificar que RiskParameters funciona"""

import sys
sys.path.insert(0, 'src')

print("Testeando imports...")

try:
    from strategies.core.enhanced_base_strategy import EnhancedBaseStrategy, RiskParameters
    print(f"✅ EnhancedBaseStrategy importado correctamente")
    print(f"   RiskParameters: {RiskParameters}")
    print(f"   EnhancedBaseStrategy.RiskParameters: {EnhancedBaseStrategy.RiskParameters}")

    from position.position_manager import PositionManager
    print(f"✅ PositionManager importado correctamente")

    # Test de instanciación de RiskParameters
    risk_params = RiskParameters(
        position_size=0.1,
        max_open_positions=5
    )
    print(f"✅ RiskParameters instanciado: {risk_params}")

    # Test con EnhancedBaseStrategy.RiskParameters
    risk_params2 = EnhancedBaseStrategy.RiskParameters(
        position_size=0.2,
        max_open_positions=3
    )
    print(f"✅ EnhancedBaseStrategy.RiskParameters instanciado: {risk_params2}")

    print("\n🎉 Todos los imports funcionan correctamente!")
    print("\n✅ El error AttributeError ha sido resuelto!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


