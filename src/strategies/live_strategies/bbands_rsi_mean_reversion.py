"""
Estrategia de reversión a la media usando Bollinger Bands + RSI + SMA.
MIGRADA al framework EnhancedBaseStrategy.

Entradas BUY cuando:
  - close <= BB inferior
  - RSI <= 40
  - close > SMA50
  - (opcional) volume > SMA20(volume)
"""

import asyncio
from typing import Dict
import pandas as pd
from datetime import datetime, timezone, timedelta

from strategies.core import EnhancedBaseStrategy
from utils.logger import Logger

logger = Logger.get_logger(__name__)


class BBANDS_RSI_MeanReversionStrategy(EnhancedBaseStrategy):
    """
    Estrategia de reversión a la media mejorada con framework modular.
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: list[str],
        timeframe: str = "1m",
        run_db_id: int | None = None,
        # Parámetros específicos de la estrategia
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_buy_threshold: float = 40.0,
        rsi_sell_threshold: float = 60.0,
        sma_period: int = 50,
        vol_sma_period: int = 20,
        enforce_volume_filter: bool = True,
        max_holding_hours: int = 48,
        **kwargs
    ):
        # Filtrar kwargs para no pasar parámetros desconocidos a EnhancedBaseStrategy
        base_kwargs = {
            'rest_client': kwargs.get('rest_client'),
            'confirmation_queue': kwargs.get('confirmation_queue'),
            'historical_candles': max(bb_period, rsi_period, sma_period, vol_sma_period) + 10,
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
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.sma_period = sma_period
        self.vol_sma_period = vol_sma_period
        self.enforce_volume_filter = enforce_volume_filter
        self.max_holding_delta = timedelta(hours=max_holding_hours)

        # Control de tiempo de posición
        self.last_buy_time: Dict[str, datetime] = {}

    def setup_indicators(self):
        """Configura los indicadores técnicos."""
        # Bollinger Bands
        self.indicators.add_bbands(length=self.bb_period, std=self.bb_std)

        # RSI
        self.indicators.add_rsi(length=self.rsi_period)

        # SMA para filtro de tendencia
        self.indicators.add_sma(length=self.sma_period, name="SMA50")

        # Volumen SMA
        if self.enforce_volume_filter:
            self.indicators.add_volume_sma(length=self.vol_sma_period, name="VOL_SMA20")

    async def check_conditions(
        self,
        symbol: str,
        candle: pd.Series,
        indicators: Dict[str, float]
    ):
        """
        Evalúa condiciones de entrada y salida.
        """
        try:
            # Extraer valores de indicadores
            rsi = indicators.get('RSI')
            bbl = indicators.get('BBL')
            bbm = indicators.get('BBM')
            bbu = indicators.get('BBU')
            sma50 = indicators.get('SMA50')
            vol_sma = indicators.get('VOL_SMA20')

            close = candle['close']
            volume = candle['volume']

            # Validar que tenemos todos los indicadores necesarios
            if None in [rsi, bbl, sma50]:
                logger.debug(f"{symbol}: Indicadores no disponibles aún")
                return

            # Log de estado
            logger.info(
                f"{symbol} | Close: {close:.4f} | RSI: {rsi:.2f} | "
                f"BB Lower: {bbl:.4f} | SMA50: {sma50:.4f}"
            )

            # =====================================================
            # CONDICIONES DE COMPRA
            # =====================================================
            buy_conditions = [
                close <= bbl,  # Precio tocó banda inferior
                rsi <= self.rsi_buy_threshold,  # RSI sobreventa
                close > sma50,  # Precio por encima de tendencia
            ]

            # Filtro de volumen opcional
            if self.enforce_volume_filter and vol_sma is not None:
                buy_conditions.append(volume > vol_sma)

            if all(buy_conditions):
                reason = (
                    f"Reversión media: close≤BB_lower ({close:.4f}≤{bbl:.4f}) & "
                    f"RSI≤{self.rsi_buy_threshold} ({rsi:.2f}) & close>SMA50"
                )

                if self.enforce_volume_filter:
                    reason += " & vol>vol_sma"

                # Emitir señal usando el framework
                await self.emit_buy(
                    symbol=symbol,
                    price=close,
                    reason=reason,
                    metadata={
                        'strategy': 'BBANDS_RSI_MeanReversion',
                        'bb_period': self.bb_period,
                        'rsi_period': self.rsi_period,
                        'rsi': rsi,
                        'bbl': bbl,
                        'sma50': sma50,
                    }
                )

                # Registrar tiempo de compra
                self.last_buy_time[symbol] = datetime.now(timezone.utc)

            # =====================================================
            # CONDICIONES DE VENTA (OPCIONAL - Actualmente deshabilitado)
            # =====================================================
            # La estrategia original solo generaba señales BUY
            # Si se desea implementar SELL, descomentar lo siguiente:
            """
            sell_conditions = [
                close >= bbu,  # Precio tocó banda superior
                rsi >= self.rsi_sell_threshold,  # RSI sobrecompra
            ]
            
            if all(sell_conditions):
                reason = f"Salida reversión: close≥BB_upper & RSI≥{self.rsi_sell_threshold}"
                await self.emit_sell(
                    symbol=symbol,
                    price=close,
                    reason=reason,
                    metadata={'strategy': 'BBANDS_RSI_MeanReversion'}
                )
            """

        except Exception as e:
            logger.error(f"Error en check_conditions para {symbol}: {e}")

    async def on_start(self):
        """Hook ejecutado al iniciar la estrategia."""
        logger.info("=" * 60)
        logger.info("ESTRATEGIA BBANDS_RSI_MeanReversion INICIADA")
        logger.info(f"  Símbolos: {self.symbols}")
        logger.info(f"  Timeframe: {self.timeframe}")
        logger.info(f"  BB Period: {self.bb_period}, Std: {self.bb_std}")
        logger.info(f"  RSI Period: {self.rsi_period}")
        logger.info(f"  RSI Umbral Compra: {self.rsi_buy_threshold}")
        logger.info(f"  SMA Period: {self.sma_period}")
        logger.info(f"  Filtro Volumen: {self.enforce_volume_filter}")
        logger.info("=" * 60)

