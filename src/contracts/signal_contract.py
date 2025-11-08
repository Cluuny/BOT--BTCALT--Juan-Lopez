# contracts/signal_contract.py
from typing import TypedDict, Optional, Union
from datetime import datetime
from strategies.BaseStrategy import BaseStrategy


class SignalContract(TypedDict):
    """
    Contrato estándar para todas las señales de trading.
    Define la estructura que DEBEN seguir todas las estrategias.
    """
    # 🔹 CAMPOS OBLIGATORIOS (todas las señales deben tenerlos)
    symbol: str
    type: str  # "BUY" or "SELL"
    price: float
    risk_params: BaseStrategy.RiskParameters

    # 🔹 CAMPOS OPCIONALES (dependen de la estrategia)
    rsi: Optional[float]  # Para estrategias RSI
    position_size_usdt: Optional[float]  # Para BTC_Daily_Open
    timestamp: Optional[str]  # Para BTC_Daily_Open
    reason: Optional[str]  # Mensaje descriptivo

    # 🔹 CAMPOS DE META-DATOS (automáticos)
    strategy_name: Optional[str]  # Nombre de la estrategia
    received_at: Optional[str]  # Timestamp de recepción


class ValidatedSignal:
    """Clase para validar y normalizar señales"""

    @staticmethod
    def validate(signal_data: dict) -> SignalContract:
        """
        Valida que una señal cumpla con el contrato básico
        y normaliza los campos opcionales - VERSIÓN MEJORADA
        """
        # 🔹 CAMPOS OBLIGATORIOS
        required_fields = ['symbol', 'type', 'price', 'risk_params']
        for field in required_fields:
            if field not in signal_data:
                raise ValueError(f"❌ Señal inválida: falta campo obligatorio '{field}'")

        # 🔹 VALIDAR TIPO
        if signal_data['type'] not in ['BUY', 'SELL']:
            raise ValueError(f"❌ Tipo de señal inválido: {signal_data['type']}")

        # 🔹 VALIDACIONES ESPECÍFICAS POR ESTRATEGIA
        strategy_name = signal_data.get('strategy_name', 'Desconocida')

        # Para estrategias RSI, validar que el RSI esté presente y sea válido
        if 'RSI' in strategy_name and 'rsi' in signal_data:
            rsi_value = signal_data['rsi']
            if rsi_value is None:
                raise ValueError("❌ Señal RSI inválida: campo 'rsi' no puede ser None")
            if not isinstance(rsi_value, (int, float)):
                raise ValueError(f"❌ Señal RSI inválida: 'rsi' debe ser numérico, recibió {type(rsi_value)}")
            if not (0 <= rsi_value <= 100):
                raise ValueError(f"❌ Señal RSI inválida: 'rsi' debe estar entre 0-100, recibió {rsi_value}")

        # 🔹 VALIDAR PRECIO
        price = signal_data['price']
        if not isinstance(price, (int, float)):
            raise ValueError(f"❌ Precio inválido: debe ser numérico, recibió {type(price)}")
        if price <= 0:
            raise ValueError(f"❌ Precio inválido: debe ser positivo, recibió {price}")

        # 🔹 NORMALIZAR CAMPOS
        normalized_signal = signal_data.copy()
        normalized_signal['price'] = float(price)

        if 'rsi' in normalized_signal and normalized_signal['rsi'] is not None:
            normalized_signal['rsi'] = float(normalized_signal['rsi'])

        # Agregar meta-datos automáticamente
        normalized_signal.setdefault('received_at', datetime.utcnow().isoformat())

        return SignalContract(**normalized_signal)

    @staticmethod
    def create_safe_signal(signal_data: dict) -> SignalContract:
        """
        Crea una señal válida con manejo de errores.
        Retorna una señal normalizada o None si es inválida.
        """
        try:
            return ValidatedSignal.validate(signal_data)
        except (ValueError, TypeError) as e:
            print(f"⚠️ Señal inválida descartada: {e}")
            print(f"📋 Datos recibidos: {signal_data}")
            return None


# 🔹 CONTRATO ESPECÍFICO POR ESTRATEGIA
class RSISignalContract(SignalContract):
    """Contrato específico para estrategias RSI"""
    rsi: float  # En RSI, este campo es obligatorio
    reason: str


class DailyOpenSignalContract(SignalContract):
    """Contrato específico para BTC Daily Open"""
    position_size_usdt: float  # Obligatorio en esta estrategia
    timestamp: str
    reason: str