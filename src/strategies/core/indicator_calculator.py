"""
Sistema declarativo para cálculo de indicadores técnicos.
Simplifica la definición y cálculo de indicadores en estrategias.
"""

from typing import Dict, List, Callable, Any, Optional
import pandas as pd
import pandas_ta as ta
from dataclasses import dataclass
from utils.logger import Logger

logger = Logger.get_logger(__name__)


@dataclass
class IndicatorConfig:
    """Configuración de un indicador técnico."""
    name: str  # Nombre del indicador (ej: "RSI", "SMA")
    function: Callable  # Función para calcularlo (ej: ta.rsi)
    params: Dict[str, Any]  # Parámetros (ej: {"length": 14})
    source: str = "close"  # Columna fuente (close, high, low, volume)
    min_periods: Optional[int] = None  # Períodos mínimos necesarios
    output_column: Optional[str] = None  # Nombre personalizado de salida


class IndicatorCalculator:
    """
    Calculadora de indicadores técnicos con sistema declarativo.

    Ejemplo de uso:
        calculator = IndicatorCalculator()
        calculator.add_indicator("RSI", ta.rsi, {"length": 14})
        calculator.add_indicator("SMA50", ta.sma, {"length": 50})
        df = calculator.compute(df)
    """

    def __init__(self):
        self.indicators: List[IndicatorConfig] = []
        self._min_required_rows = 0

    def add_indicator(
        self,
        name: str,
        function: Callable,
        params: Dict[str, Any],
        source: str = "close",
        output_column: Optional[str] = None,
    ) -> 'IndicatorCalculator':
        """
        Añade un indicador a calcular.

        Args:
            name: Nombre descriptivo del indicador
            function: Función de pandas_ta (ej: ta.rsi, ta.sma, ta.bbands)
            params: Diccionario con parámetros (ej: {"length": 14})
            source: Columna del DataFrame a usar como entrada
            output_column: Nombre personalizado para la columna de salida

        Returns:
            self para encadenar llamadas
        """
        # Extraer período mínimo del parámetro 'length' si existe
        min_periods = params.get("length", params.get("period", 0))

        indicator = IndicatorConfig(
            name=name,
            function=function,
            params=params,
            source=source,
            min_periods=min_periods,
            output_column=output_column or name,
        )

        self.indicators.append(indicator)

        # Actualizar mínimo requerido
        if min_periods:
            self._min_required_rows = max(self._min_required_rows, min_periods)

        logger.debug(f"Indicador añadido: {name} con params {params}")
        return self

    def add_sma(self, length: int, source: str = "close", name: Optional[str] = None) -> 'IndicatorCalculator':
        """Atajo para añadir SMA."""
        return self.add_indicator(
            name=name or f"SMA{length}",
            function=ta.sma,
            params={"length": length},
            source=source,
        )

    def add_ema(self, length: int, source: str = "close", name: Optional[str] = None) -> 'IndicatorCalculator':
        """Atajo para añadir EMA."""
        return self.add_indicator(
            name=name or f"EMA{length}",
            function=ta.ema,
            params={"length": length},
            source=source,
        )

    def add_rsi(self, length: int = 14, name: str = "RSI") -> 'IndicatorCalculator':
        """Atajo para añadir RSI."""
        return self.add_indicator(
            name=name,
            function=ta.rsi,
            params={"length": length},
            source="close",
        )

    def add_bbands(
        self,
        length: int = 20,
        std: float = 2.0,
        name: str = "BBANDS"
    ) -> 'IndicatorCalculator':
        """Atajo para añadir Bollinger Bands."""
        return self.add_indicator(
            name=name,
            function=ta.bbands,
            params={"length": length, "std": std},
            source="close",
        )

    def add_macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        name: str = "MACD"
    ) -> 'IndicatorCalculator':
        """Atajo para añadir MACD."""
        return self.add_indicator(
            name=name,
            function=ta.macd,
            params={"fast": fast, "slow": slow, "signal": signal},
            source="close",
        )

    def add_atr(self, length: int = 14, name: str = "ATR") -> 'IndicatorCalculator':
        """Atajo para añadir ATR (requiere high, low, close)."""
        return self.add_indicator(
            name=name,
            function=ta.atr,
            params={"length": length},
            source="close",  # ATR usa high, low, close internamente
        )

    def add_volume_sma(self, length: int = 20, name: Optional[str] = None) -> 'IndicatorCalculator':
        """Atajo para añadir SMA de volumen."""
        return self.add_indicator(
            name=name or f"VOL_SMA{length}",
            function=ta.sma,
            params={"length": length},
            source="volume",
        )

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula todos los indicadores configurados.

        Args:
            df: DataFrame con datos OHLCV

        Returns:
            DataFrame con indicadores añadidos
        """
        if len(df) < 5:
            logger.warning(f"DataFrame muy pequeño ({len(df)} filas), algunos indicadores pueden fallar")
            return df

        result = df.copy()

        for indicator in self.indicators:
            try:
                # Verificar si hay suficientes datos
                if indicator.min_periods and len(result) < indicator.min_periods:
                    logger.debug(
                        f"Insuficientes datos para {indicator.name}: "
                        f"{len(result)} < {indicator.min_periods}"
                    )
                    result[indicator.output_column] = None
                    continue

                # Obtener serie fuente
                source_series = result[indicator.source]

                # Calcular indicador
                calculated = indicator.function(source_series, **indicator.params)

                # Manejar resultados múltiples (ej: Bollinger Bands devuelve DataFrame)
                if isinstance(calculated, pd.DataFrame):
                    # Para Bollinger Bands y otros que devuelven múltiples columnas
                    self._handle_multi_column_indicator(result, calculated, indicator)
                elif isinstance(calculated, pd.Series):
                    # Indicador simple (SMA, RSI, etc.)
                    result[indicator.output_column] = calculated
                else:
                    logger.warning(f"Resultado inesperado de {indicator.name}: {type(calculated)}")

            except Exception as e:
                logger.error(f"Error calculando {indicator.name}: {e}")
                result[indicator.output_column] = None

        return result.reset_index(drop=True)

    def _handle_multi_column_indicator(
        self,
        result: pd.DataFrame,
        calculated: pd.DataFrame,
        indicator: IndicatorConfig
    ):
        """Maneja indicadores que devuelven múltiples columnas (ej: Bollinger Bands)."""
        if indicator.name == "BBANDS" or "bbands" in indicator.function.__name__.lower():
            # Bollinger Bands específicamente
            suffix = f"{indicator.params.get('length', 20)}_{indicator.params.get('std', 2.0)}"

            # Buscar columnas generadas por pandas_ta
            bbl_col = next((c for c in calculated.columns if c.startswith('BBL_')), None)
            bbm_col = next((c for c in calculated.columns if c.startswith('BBM_')), None)
            bbu_col = next((c for c in calculated.columns if c.startswith('BBU_')), None)

            if bbl_col and bbm_col and bbu_col:
                result['BBL'] = calculated[bbl_col]
                result['BBM'] = calculated[bbm_col]
                result['BBU'] = calculated[bbu_col]
                logger.debug(f"Bollinger Bands añadidas: BBL, BBM, BBU")
            else:
                logger.warning(f"No se encontraron columnas BB esperadas en: {calculated.columns}")

        elif indicator.name == "MACD" or "macd" in indicator.function.__name__.lower():
            # MACD devuelve MACD, señal e histograma
            macd_col = next((c for c in calculated.columns if c.startswith('MACD_')), None)
            signal_col = next((c for c in calculated.columns if c.startswith('MACDs_')), None)
            hist_col = next((c for c in calculated.columns if c.startswith('MACDh_')), None)

            if macd_col:
                result['MACD'] = calculated[macd_col]
            if signal_col:
                result['MACD_signal'] = calculated[signal_col]
            if hist_col:
                result['MACD_hist'] = calculated[hist_col]

        else:
            # Para otros indicadores multi-columna, usar el output_column como prefijo
            for col in calculated.columns:
                result[f"{indicator.output_column}_{col}"] = calculated[col]

    def get_min_required_rows(self) -> int:
        """Retorna el número mínimo de filas necesarias para calcular todos los indicadores."""
        return self._min_required_rows

    def get_indicator_names(self) -> List[str]:
        """Retorna lista de nombres de indicadores configurados."""
        return [ind.output_column for ind in self.indicators]

    def clear(self):
        """Limpia todos los indicadores configurados."""
        self.indicators.clear()
        self._min_required_rows = 0


class IndicatorPresets:
    """Presets comunes de indicadores para estrategias populares."""

    @staticmethod
    def mean_reversion() -> IndicatorCalculator:
        """Preset para estrategias de reversión a la media."""
        calc = IndicatorCalculator()
        calc.add_bbands(length=20, std=2.0)
        calc.add_rsi(length=14)
        calc.add_sma(length=50, name="SMA50")
        calc.add_volume_sma(length=20)
        return calc

    @staticmethod
    def trend_following() -> IndicatorCalculator:
        """Preset para estrategias de seguimiento de tendencia."""
        calc = IndicatorCalculator()
        calc.add_ema(length=9, name="EMA9")
        calc.add_ema(length=21, name="EMA21")
        calc.add_ema(length=50, name="EMA50")
        calc.add_macd()
        calc.add_atr()
        return calc

    @staticmethod
    def momentum() -> IndicatorCalculator:
        """Preset para estrategias de momentum."""
        calc = IndicatorCalculator()
        calc.add_rsi(length=14)
        calc.add_macd()
        calc.add_sma(length=20, name="SMA20")
        calc.add_volume_sma(length=20)
        return calc

    @staticmethod
    def scalping() -> IndicatorCalculator:
        """Preset para estrategias de scalping."""
        calc = IndicatorCalculator()
        calc.add_ema(length=5, name="EMA5")
        calc.add_ema(length=13, name="EMA13")
        calc.add_rsi(length=7)
        calc.add_volume_sma(length=10)
        return calc

