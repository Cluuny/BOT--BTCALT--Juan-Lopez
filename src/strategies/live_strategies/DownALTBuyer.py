import asyncio
from utils.logger import Logger
from typing import Dict
import pandas as pd

from strategies.core import EnhancedBaseStrategy

logger = Logger.get_logger(__name__)


class DownALTBuyer(EnhancedBaseStrategy):
    def __init__(
            self,
            signal_queue: asyncio.Queue,
            bot_id: int,
            symbols: list[str],
            timeframe: str = "1m",
            run_db_id: int | None = None,
            # Parámetros específicos de la estrategia
            entry_threshold: float = -1.0,  # -1% de cambio para entrar
            exit_threshold: float = 2.0,  # +2% de cambio para salir
            position_size_percent: float = 100.0,  # Porcentaje del capital a usar
            base_capital: float = 10.0,  # Capital base en USDT
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
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size_percent = position_size_percent
        self.base_capital = base_capital

        # Cache para cambios porcentuales
        self.price_changes: Dict[str, float] = {}

    def setup_indicators(self):
        """
        Configura los indicadores técnicos.
        En este caso, usaremos el cambio porcentual de precio de 24 h como indicador principal.
        """
        # Para esta estrategia simple, no necesitamos indicadores técnicos complejos
        # El cambio porcentual lo obtendremos directamente de la API
        pass

    async def check_conditions(
            self,
            symbol: str,
            candle: pd.Series,
            indicators: Dict[str, float]
    ):
        """
        Evalúa condiciones de entrada y salida basadas en el cambio porcentual de precio.
        """
        try:
            # Obtener el cambio porcentual actual del precio
            current_change = await self._get_current_price_change(symbol)

            if current_change is None:
                raise Exception("No se pudo obtener el cambio porcentual actual")

            logger.debug(f"{self.symbols}")
            logger.info(current_change)

            # Lógica de la estrategia
            # if current_change <= self.entry_threshold:
            #     # Condición de COMPRA: el precio ha bajado más del threshold negativo
            #     reason = f"Precio bajó {current_change:.2f}% (umbral: {self.entry_threshold}%)"
            #     await self.emit_buy(
            #         symbol=symbol,
            #         price=candle['close'],
            #         reason=reason,
            #         metadata={
            #             'price_change_24h': current_change,
            #             'entry_threshold': self.entry_threshold,
            #             'strategy': 'DownALTBuyer'
            #         }
            #     )
            #
            # elif current_change >= self.exit_threshold:
            #     # Condición de VENTA: el precio ha subido más del threshold positivo
            #     reason = f"Precio subió {current_change:.2f}% (umbral: {self.exit_threshold}%)"
            #     await self.emit_sell(
            #         symbol=symbol,
            #         price=candle['close'],
            #         reason=reason,
            #         metadata={
            #             'price_change_24h': current_change,
            #             'exit_threshold': self.exit_threshold,
            #             'strategy': 'DownALTBuyer'
            #         }
            #     )

        except Exception as e:
            logger.error(f"Error en check_conditions para {symbol}: {e}")

    async def _get_current_price_change(self, symbol: str) -> float | None:
        """
        Obtiene el cambio porcentual de precio de 24 h desde Binance.
        """
        try:
            # Usar el metodo del DataManager para obtener el cambio porcentual
            # Nota: Esto puede necesitar ajustes dependiendo de tu implementación real
            change_percent = self.data_manager.get_price_changue_percent(symbol)

            if change_percent is not None:
                self.price_changes[symbol] = change_percent
                return change_percent
            else:
                # Fallback: calcular manualmente si la API falla
                return await self._calculate_price_change_fallback(symbol)

        except Exception as e:
            logger.warning(f"No se pudo obtener cambio porcentual para {symbol}: {e}")
            return self.price_changes.get(symbol)  # Usar último valor conocido

    async def _calculate_price_change_fallback(self, symbol: str) -> float | None:
        """
        Calcula el cambio porcentual manualmente como fallback.
        """
        try:
            df = self.data_manager.get_candles(symbol)
            if df is None or len(df) < 2:
                return None

            # Calcular cambio porcentual basado en velas recientes
            # (esto es una aproximación, lo ideal es usar la API)
            current_close = df.iloc[-1]['close']

            # Buscar un precio de referencia (Ejemplo: hace 24 periodos si es 1 h)
            lookback = min(24, len(df) - 1)
            reference_close = df.iloc[-lookback]['close']

            price_change = ((current_close - reference_close) / reference_close) * 100
            return price_change

        except Exception as e:
            logger.error(f"Error calculando cambio porcentual fallback: {e}")
            return None

    async def on_candle_update(self, symbol: str, candle: pd.Series, indicators: Dict[str, float]):
        """
        Hook opcional para lógica adicional en cada actualización.
        """
        # Puedes añadir lógica adicional aquí si necesitas
        # Por ejemplo, logging específico o métricas
        current_change = await self._get_current_price_change(symbol)
        if current_change is not None:
            logger.debug(f"{symbol}: Cambio porcentual actual = {current_change:.2f}%")