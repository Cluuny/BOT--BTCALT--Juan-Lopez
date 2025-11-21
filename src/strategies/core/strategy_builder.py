"""
Strategy Builder: Constructor declarativo de estrategias.

Para estrategias MUY simples, puedes definirlas completamente con un diccionario.
No necesitas escribir una clase completa.
"""

import asyncio
from typing import Dict, List, Callable, Any
from strategies.core import EnhancedBaseStrategy
from utils.logger import Logger

logger = Logger.get_logger(__name__)


class StrategyBuilder:
    """
    Constructor fluido para crear estrategias sin escribir clases.

    Ejemplo:
        strategy = (
            StrategyBuilder("MyStrategy")
            .add_rsi(14)
            .add_sma(50)
            .on_buy(lambda candle, ind: ind['RSI'] < 30 and candle['close'] < ind['SMA50'])
            .build(signal_queue, bot_id, symbols)
        )
    """

    def __init__(self, name: str):
        self.name = name
        self._indicators = []
        self._buy_condition: Callable = None
        self._sell_condition: Callable = None
        self._timeframe = "1m"
        self._metadata = {}

    def add_rsi(self, length: int = 14, name: str = "RSI"):
        """Añade RSI."""
        self._indicators.append(('rsi', {'length': length}, name))
        return self

    def add_sma(self, length: int, name: str = None):
        """Añade SMA."""
        self._indicators.append(('sma', {'length': length}, name or f"SMA{length}"))
        return self

    def add_ema(self, length: int, name: str = None):
        """Añade EMA."""
        self._indicators.append(('ema', {'length': length}, name or f"EMA{length}"))
        return self

    def add_bbands(self, length: int = 20, std: float = 2.0):
        """Añade Bollinger Bands."""
        self._indicators.append(('bbands', {'length': length, 'std': std}, 'BBANDS'))
        return self

    def add_macd(self, fast: int = 12, slow: int = 26, signal: int = 9):
        """Añade MACD."""
        self._indicators.append(('macd', {'fast': fast, 'slow': slow, 'signal': signal}, 'MACD'))
        return self

    def set_timeframe(self, timeframe: str):
        """Establece el timeframe."""
        self._timeframe = timeframe
        return self

    def on_buy(self, condition: Callable[[Dict, Dict], bool]):
        """
        Define condición de compra.

        Args:
            condition: Función que recibe (candle, indicators) y retorna bool

        Ejemplo:
            .on_buy(lambda c, i: i['RSI'] < 30 and c['close'] < i['SMA50'])
        """
        self._buy_condition = condition
        return self

    def on_sell(self, condition: Callable[[Dict, Dict], bool]):
        """Define condición de venta."""
        self._sell_condition = condition
        return self

    def build(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: List[str],
        **kwargs
    ) -> 'DynamicStrategy':
        """Construye la estrategia."""
        return DynamicStrategy(
            name=self.name,
            signal_queue=signal_queue,
            bot_id=bot_id,
            symbols=symbols,
            timeframe=self._timeframe,
            indicators=self._indicators,
            buy_condition=self._buy_condition,
            sell_condition=self._sell_condition,
            **kwargs
        )


class DynamicStrategy(EnhancedBaseStrategy):
    """Estrategia generada dinámicamente por StrategyBuilder."""

    def __init__(
        self,
        name: str,
        indicators: List,
        buy_condition: Callable,
        sell_condition: Callable,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.strategy_name = name
        self._indicator_configs = indicators
        self._buy_condition = buy_condition
        self._sell_condition = sell_condition

        logger.info(f"Estrategia dinámica '{name}' creada con {len(indicators)} indicadores")

    def setup_indicators(self):
        """Configura indicadores basado en la lista proporcionada."""
        for ind_type, params, name in self._indicator_configs:
            if ind_type == 'rsi':
                self.indicators.add_rsi(**params)
            elif ind_type == 'sma':
                self.indicators.add_sma(**params, name=name)
            elif ind_type == 'ema':
                self.indicators.add_ema(**params, name=name)
            elif ind_type == 'bbands':
                self.indicators.add_bbands(**params)
            elif ind_type == 'macd':
                self.indicators.add_macd(**params)
            else:
                logger.warning(f"Tipo de indicador desconocido: {ind_type}")

    async def check_conditions(self, symbol: str, candle, indicators: dict):
        """Evalúa condiciones definidas por el usuario."""
        try:
            # Convertir candle (Series) a dict
            candle_dict = candle.to_dict()

            # Condición de compra
            if self._buy_condition and self._buy_condition(candle_dict, indicators):
                reason = f"{self.strategy_name}: Condición BUY cumplida"
                await self.emit_buy(symbol, candle_dict['close'], reason)

            # Condición de venta
            if self._sell_condition and self._sell_condition(candle_dict, indicators):
                reason = f"{self.strategy_name}: Condición SELL cumplida"
                await self.emit_sell(symbol, candle_dict['close'], reason)

        except Exception as e:
            logger.error(f"Error evaluando condiciones: {e}")


# ==================== EJEMPLOS DE USO ====================

def create_rsi_oversold_strategy(
    signal_queue: asyncio.Queue,
    bot_id: int,
    symbols: List[str]
):
    """
    Estrategia simple: compra cuando RSI < 30.

    ¡COMPLETAMENTE DEFINIDA EN 5 LÍNEAS!
    """
    return (
        StrategyBuilder("RSI_Oversold")
        .add_rsi(14)
        .on_buy(lambda c, i: i.get('RSI', 100) < 30)
        .build(signal_queue, bot_id, symbols)
    )


def create_ema_crossover_strategy(
    signal_queue: asyncio.Queue,
    bot_id: int,
    symbols: List[str]
):
    """
    Estrategia de cruce de EMAs.

    Compra: EMA rápida cruza por encima de EMA lenta
    Vende: EMA rápida cruza por debajo de EMA lenta
    """
    builder = StrategyBuilder("EMA_Crossover")
    builder.add_ema(9, "EMA_fast")
    builder.add_ema(21, "EMA_slow")

    # Compra cuando EMA rápida > EMA lenta
    builder.on_buy(lambda c, i: i.get('EMA_fast', 0) > i.get('EMA_slow', 0))

    # Vende cuando EMA rápida < EMA lenta
    builder.on_sell(lambda c, i: i.get('EMA_fast', float('inf')) < i.get('EMA_slow', 0))

    return builder.build(signal_queue, bot_id, symbols)


def create_bbands_breakout_strategy(
    signal_queue: asyncio.Queue,
    bot_id: int,
    symbols: List[str]
):
    """
    Estrategia de breakout de Bollinger Bands.

    Compra: Precio rompe banda superior
    Vende: Precio rompe banda inferior
    """
    return (
        StrategyBuilder("BBands_Breakout")
        .add_bbands(20, 2.0)
        .on_buy(lambda c, i: c.get('close', 0) > i.get('BBU', float('inf')))
        .on_sell(lambda c, i: c.get('close', float('inf')) < i.get('BBL', 0))
        .build(signal_queue, bot_id, symbols)
    )


def create_custom_complex_strategy(
    signal_queue: asyncio.Queue,
    bot_id: int,
    symbols: List[str]
):
    """
    Estrategia más compleja con múltiples condiciones.

    Compra cuando:
    - RSI < 40 (sobreventa)
    - Precio debajo de SMA50
    - MACD histograma positivo (momentum)
    """
    builder = StrategyBuilder("Complex_Reversal")
    builder.add_rsi(14)
    builder.add_sma(50, "SMA50")
    builder.add_macd()

    def buy_condition(candle, indicators):
        rsi = indicators.get('RSI', 100)
        sma50 = indicators.get('SMA50', 0)
        macd_hist = indicators.get('MACD_hist', -1)
        close = candle.get('close', 0)

        return (
            rsi < 40 and
            close < sma50 and
            macd_hist > 0
        )

    builder.on_buy(buy_condition)

    return builder.build(signal_queue, bot_id, symbols)


# ==================== UTILITY: ESTRATEGIA DESDE JSON ====================

def strategy_from_config(config: Dict, signal_queue: asyncio.Queue, bot_id: int, symbols: List[str]):
    """
    Crea una estrategia desde configuración JSON/Dict.

    Ejemplo de config:
    {
        "name": "My Strategy",
        "timeframe": "5m",
        "indicators": [
            {"type": "rsi", "length": 14},
            {"type": "sma", "length": 50, "name": "SMA50"}
        ],
        "buy_rules": [
            {"indicator": "RSI", "operator": "<", "value": 30},
            {"indicator": "close", "operator": "<", "value": "SMA50"}
        ]
    }
    """
    builder = StrategyBuilder(config.get("name", "CustomStrategy"))

    if "timeframe" in config:
        builder.set_timeframe(config["timeframe"])

    # Añadir indicadores
    for ind_config in config.get("indicators", []):
        ind_type = ind_config["type"]
        if ind_type == "rsi":
            builder.add_rsi(ind_config.get("length", 14))
        elif ind_type == "sma":
            builder.add_sma(ind_config["length"], ind_config.get("name"))
        elif ind_type == "ema":
            builder.add_ema(ind_config["length"], ind_config.get("name"))
        elif ind_type == "bbands":
            builder.add_bbands(ind_config.get("length", 20), ind_config.get("std", 2.0))
        elif ind_type == "macd":
            builder.add_macd()

    # Construir condición de compra desde reglas
    buy_rules = config.get("buy_rules", [])

    def dynamic_buy_condition(candle, indicators):
        for rule in buy_rules:
            indicator = rule["indicator"]
            operator = rule["operator"]
            value = rule["value"]

            # Obtener valor actual del indicador
            if indicator == "close":
                current = candle.get("close", 0)
            else:
                current = indicators.get(indicator)

            if current is None:
                return False

            # Comparar con valor de referencia
            if isinstance(value, str):
                # Es referencia a otro indicador
                ref_value = indicators.get(value)
                if ref_value is None:
                    return False
            else:
                ref_value = value

            # Evaluar operador
            if operator == "<" and not (current < ref_value):
                return False
            elif operator == ">" and not (current > ref_value):
                return False
            elif operator == "<=" and not (current <= ref_value):
                return False
            elif operator == ">=" and not (current >= ref_value):
                return False
            elif operator == "==" and not (abs(current - ref_value) < 0.0001):
                return False

        return True  # Todas las reglas se cumplieron

    if buy_rules:
        builder.on_buy(dynamic_buy_condition)

    return builder.build(signal_queue, bot_id, symbols)

