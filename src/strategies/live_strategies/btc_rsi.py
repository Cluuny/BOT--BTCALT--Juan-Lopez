"""
Estrategia basada en RSI aplicada a múltiples símbolos.
MIGRADA al framework EnhancedBaseStrategy.

Señales:
  - BUY cuando RSI <= oversold (30)
  - SELL cuando RSI >= overbought (70)
"""

import asyncio
from typing import Dict
import pandas as pd

from strategies.core import EnhancedBaseStrategy
from utils.logger import Logger

logger = Logger.get_logger(__name__)


class BTC_RSI_Strategy(EnhancedBaseStrategy):
    """
    Estrategia RSI simple mejorada con framework modular.
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: list[str],
        timeframe: str = "1m",
        run_db_id: int | None = None,
        # Parámetros específicos de la estrategia
        rsi_period: int = 14,
        overbought: float = 70,
        oversold: float = 30,
        **kwargs
    ):
        # Filtrar kwargs para no pasar parámetros desconocidos a EnhancedBaseStrategy
        base_kwargs = {
            'rest_client': kwargs.get('rest_client'),
            'confirmation_queue': kwargs.get('confirmation_queue'),
            'historical_candles': rsi_period + 10,
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
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold

    def setup_indicators(self):
        """Configura los indicadores técnicos."""
        # Solo necesitamos RSI
        self.indicators.add_rsi(length=self.rsi_period)

    async def check_conditions(
        self,
        symbol: str,
        candle: pd.Series,
        indicators: Dict[str, float]
    ):
        """
        Evalúa condiciones de entrada y salida basadas en RSI.
        """
        try:
            # Extraer valores
            rsi = indicators.get('RSI')
            close = candle['close']

            # Validar que tenemos RSI
            if rsi is None:
                logger.debug(f"{symbol}: RSI no disponible aún")
                return

            # Log de estado
            logger.info(
                f"{symbol} | Close: {close:.2f} | RSI: {rsi:.2f}"
            )

            # =====================================================
            # CONDICIONES DE VENTA (Sobrecompra)
            # =====================================================
            if rsi >= self.overbought:
                reason = f"RSI sobrecompra: {rsi:.2f} >= {self.overbought}"
                await self.emit_sell(
                    symbol=symbol,
                    price=close,
                    reason=reason,
                    metadata={
                        'strategy': 'BTC_RSI',
                        'rsi_period': self.rsi_period,
                        'rsi': rsi,
                        'overbought': self.overbought,
                    }
                )

            # =====================================================
            # CONDICIONES DE COMPRA (Sobreventa)
            # =====================================================
            elif rsi <= self.oversold:
                reason = f"RSI sobreventa: {rsi:.2f} <= {self.oversold}"
                await self.emit_buy(
                    symbol=symbol,
                    price=close,
                    reason=reason,
                    metadata={
                        'strategy': 'BTC_RSI',
                        'rsi_period': self.rsi_period,
                        'rsi': rsi,
                        'oversold': self.oversold,
                    }
                )

        except Exception as e:
            logger.error(f"Error en check_conditions para {symbol}: {e}")

    async def on_start(self):
        """Hook ejecutado al iniciar la estrategia."""
        logger.info("=" * 60)
        logger.info("ESTRATEGIA BTC_RSI INICIADA")
        logger.info(f"  Símbolos: {self.symbols}")
        logger.info(f"  Timeframe: {self.timeframe}")
        logger.info(f"  RSI Period: {self.rsi_period}")
        logger.info(f"  Overbought: {self.overbought}")
        logger.info(f"  Oversold: {self.oversold}")
        logger.info("=" * 60)

