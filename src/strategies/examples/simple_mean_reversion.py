"""
EJEMPLO: Estrategia de Reversión a la Media usando el framework mejorado.

Este ejemplo muestra cómo crear una estrategia completa con muy poco código
usando los componentes modulares.

Compara esto con bbands_rsi_mean_reversion.py - la misma lógica pero mucho más simple.
"""

import asyncio
from strategies.core import EnhancedBaseStrategy
from utils.logger import Logger

logger = Logger.get_logger(__name__)


class SimpleMeanReversionStrategy(EnhancedBaseStrategy):
    """
    Estrategia simple de reversión a la media.

    Condiciones de entrada (BUY):
    - Precio toca o cruza banda inferior de Bollinger
    - RSI <= 40 (sobreventa)
    - Precio por encima de SMA50 (filtro de tendencia alcista)
    - Volumen > promedio (opcional)

    Solo definimos QUÉ indicadores usar y CUÁNDO comprar/vender.
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: list[str],
        timeframe: str = "1m",
        run_db_id: int | None = None,
        # Parámetros específicos de la estrategia
        rsi_oversold: float = 40.0,
        rsi_overbought: float = 60.0,
        bb_period: int = 20,
        bb_std: float = 2.0,
        sma_period: int = 50,
        use_volume_filter: bool = True,
        **kwargs
    ):
        # Filtrar kwargs para no pasar parámetros desconocidos a EnhancedBaseStrategy
        base_kwargs = {
            'rest_client': kwargs.get('rest_client'),
            'confirmation_queue': kwargs.get('confirmation_queue'),
            'historical_candles': kwargs.get('historical_candles', 100),
        }
        # Eliminar None values
        base_kwargs = {k: v for k, v in base_kwargs.items() if v is not None}

        super().__init__(
            signal_queue=signal_queue,
            bot_id=bot_id,
            symbols=symbols,
            timeframe=timeframe,
            run_db_id=run_db_id,
            **base_kwargs
        )

        # Parámetros de la estrategia
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.sma_period = sma_period
        self.use_volume_filter = use_volume_filter

    def setup_indicators(self):
        """
        El cálculo, manejo de NaN, formato de columnas, etc. es automático.
        """
        # Bollinger Bands
        self.indicators.add_bbands(length=self.bb_period, std=self.bb_std)

        # RSI
        self.indicators.add_rsi(length=14)

        # SMA para filtro de tendencia
        self.indicators.add_sma(length=self.sma_period, name="SMA50")

        # Volumen promedio
        if self.use_volume_filter:
            self.indicators.add_volume_sma(length=20, name="VOL_SMA")

        logger.info(
            f"Indicadores configurados: BB({self.bb_period},{self.bb_std}), "
            f"RSI(14), SMA({self.sma_period})"
        )

    async def check_conditions(self, symbol: str, candle, indicators: dict):
        """
        Solo se definen las condiciones de Trading
        """
        # Extraer valores (ya validados, sin None)
        close = candle['close']
        rsi = indicators.get('RSI')
        bb_lower = indicators.get('BBL')
        bb_upper = indicators.get('BBU')
        sma50 = indicators.get('SMA50')
        volume = candle.get('volume', 0)
        vol_sma = indicators.get('VOL_SMA')

        # Validar que tenemos todos los indicadores necesarios
        if None in [rsi, bb_lower, bb_upper, sma50]:
            logger.debug(f"{symbol}: Esperando inicialización de indicadores...")
            return

        # ========== CONDICIÓN DE COMPRA ==========
        conditions_buy = [
            close <= bb_lower,  # Precio en banda inferior
            rsi <= self.rsi_oversold,  # RSI en sobreventa
            close > sma50,  # Tendencia alcista (filtro)
        ]

        # Filtro de volumen opcional
        if self.use_volume_filter and vol_sma is not None:
            conditions_buy.append(volume > vol_sma)

        if all(conditions_buy):
            reason = (
                f"Reversión media: close≤BB_lower({bb_lower:.2f}), "
                f"RSI={rsi:.1f}≤{self.rsi_oversold}, "
                f"close>{sma50:.2f}"
            )

            await self.emit_buy(symbol, close, reason)

            # Pequeña pausa para no saturar
            await asyncio.sleep(0.1)

        # ========== CONDICIÓN DE VENTA (opcional, deshabilitada por defecto) ==========
        # Puedes activar lógica de salida aquí si lo deseas
        """
        conditions_sell = [
            close >= bb_upper,
            rsi >= self.rsi_overbought,
        ]
        
        if all(conditions_sell):
            await self.emit_sell(
                symbol, close, 
                f"Reversión media: close≥BB_upper, RSI={rsi:.1f}"
            )
        """


# ==================== EJEMPLO CON PRESETS ====================

class QuickScalpingStrategy(EnhancedBaseStrategy):
    """Estrategia de scalping usando preset de indicadores."""

    def setup_indicators(self):
        # Usar preset de scalping - ¡Una sola línea!
        from strategies.core.indicator_calculator import IndicatorPresets
        self.indicators = IndicatorPresets.scalping()

    async def check_conditions(self, symbol: str, candle, indicators: dict):
        ema5 = indicators.get('EMA5')
        ema13 = indicators.get('EMA13')
        rsi = indicators.get('RSI')

        if None in [ema5, ema13, rsi]:
            return

        close = candle['close']

        # Cruce alcista de EMAs + RSI bajo
        if ema5 > ema13 and rsi < 50:
            await self.emit_buy(symbol, close, f"EMA5>{ema13}, RSI={rsi:.1f}")


# ==================== EJEMPLO CON HOOKS PERSONALIZADOS ====================

class AdvancedMeanReversionStrategy(SimpleMeanReversionStrategy):
    """Estrategia con lógica adicional en hooks."""

    async def on_start(self):
        """Hook de inicialización - puedes cargar estado de DB, configuración, etc."""
        logger.info("Cargando configuración personalizada...")
        self.trade_count = 0
        self.max_trades_per_day = 10

    async def on_candle_update(self, symbol: str, candle, indicators: dict):
        """Hook después de cada vela - útil para tracking, logs, análisis, etc."""
        # Por ejemplo: guardar métricas en DB, enviar a dashboard, etc.
        if self.trade_count >= self.max_trades_per_day:
            logger.warning(f"Límite diario de trades alcanzado ({self.max_trades_per_day})")

    async def check_conditions(self, symbol: str, candle, indicators: dict):
        # Lógica normal de la estrategia
        if self.trade_count >= self.max_trades_per_day:
            return  # No operar más hoy

        # Llamar a la lógica de la clase padre
        await super().check_conditions(symbol, candle, indicators)

        # Incrementar contador si emitimos señal
        # (esto es simplificado, en producción usarías confirmaciones)
        self.trade_count += 1


