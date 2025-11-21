"""
Gestor unificado de datos históricos y en tiempo real.
Abstrae la complejidad de cargar, actualizar y mantener DataFrames de velas.
"""

from typing import Dict, List, Optional
import pandas as pd
import asyncio
from datetime import datetime, timezone
from utils.logger import Logger
from data.rest_data_provider import BinanceRESTClient

logger = Logger.get_logger(__name__)


class DataManager:
    """
    Gestiona la carga y actualización de datos de mercado.

    Características:
    - Carga histórica automática
    - Actualización incremental de velas
    - Manejo de múltiples símbolos
    - Límite automático de tamaño de DataFrame
    - Gestión robusta de formatos de datos
    """

    def __init__(
        self,
        rest_client: Optional[BinanceRESTClient] = None,
        max_candles_per_symbol: int = 500,
        default_interval: str = "1m",
    ):
        """
        Args:
            rest_client: Cliente REST de Binance para datos históricos
            max_candles_per_symbol: Máximo de velas a mantener por símbolo
            default_interval: Intervalo por defecto (1m, 5m, 1h, 1d, etc.)
        """
        self.rest_client = rest_client or BinanceRESTClient()
        self.max_candles = max_candles_per_symbol
        self.default_interval = default_interval

        # Almacenamiento de datos
        self.candles: Dict[str, pd.DataFrame] = {}
        self._last_update_time: Dict[str, datetime] = {}

    async def load_historical_data(
        self,
        symbols: List[str],
        interval: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, pd.DataFrame]:
        """
        Carga datos históricos para los símbolos especificados.

        Args:
            symbols: Lista de símbolos (ej: ["BTCUSDT", "ETHUSDT"])
            interval: Intervalo de velas (1m, 5m, 1h, 1d). Usa default_interval si no se especifica
            limit: Cantidad de velas a cargar

        Returns:
            Diccionario {symbol: DataFrame}
        """
        interval = interval or self.default_interval
        binance_interval = self._convert_interval_format(interval)

        logger.info(f"Cargando {limit} velas de {interval} para {len(symbols)} símbolos...")

        try:
            # Usar método async si está disponible
            if hasattr(self.rest_client, 'async_get_all_klines'):
                response = await self.rest_client.async_get_all_klines(
                    list_symbols=symbols,
                    interval=binance_interval,
                    limit=limit
                )
            else:
                # Fallback a método síncrono en executor
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    self.rest_client.get_all_klines,
                    symbols,
                    binance_interval,
                    limit
                )

            # Procesar respuesta
            for symbol, data in response.items():
                df = self._convert_to_dataframe(data)
                self.candles[symbol] = df
                self._last_update_time[symbol] = datetime.now(timezone.utc)

                logger.info(f"{symbol}: {len(df)} velas cargadas")

            return self.candles

        except Exception as e:
            logger.error(f"Error cargando datos históricos: {e}")
            raise

    def update_candle(self, symbol: str, kline_data: any) -> pd.DataFrame:
        """
        Actualiza o añade una nueva vela para un símbolo.

        Args:
            symbol: Símbolo a actualizar
            kline_data: Datos de vela (puede ser lista, tupla o dict)

        Returns:
            DataFrame actualizado
        """
        try:
            # Parsear datos de vela
            candle = self._parse_kline_data(kline_data)

            if candle is None:
                logger.warning(f"No se pudo parsear vela para {symbol}")
                return self.candles.get(symbol, pd.DataFrame())

            # Crear DataFrame si no existe
            if symbol not in self.candles:
                logger.info(f"Creando nuevo DataFrame para {symbol}")
                df = pd.DataFrame([candle])
                self.candles[symbol] = df
                return df

            df = self.candles[symbol].copy()

            # Buscar si ya existe una vela con este close_time
            close_time = candle.get("close_time")
            mask = df["close_time"] == close_time

            if mask.any():
                # Actualizar vela existente
                idx = mask.idxmax()
                for col, value in candle.items():
                    df.at[idx, col] = value
                logger.debug(f"{symbol}: Vela existente actualizada (close_time={close_time})")
            else:
                # Añadir nueva vela
                df = df.reset_index(drop=True)
                df.loc[len(df)] = candle

                # Limitar tamaño del DataFrame
                if len(df) > self.max_candles:
                    df = df.iloc[-self.max_candles:].copy()
                    logger.debug(f"{symbol}: DataFrame recortado a {self.max_candles} velas")

                logger.debug(f"{symbol}: Nueva vela añadida (total: {len(df)})")

            # Resetear índice y guardar
            df = df.reset_index(drop=True)
            self.candles[symbol] = df
            self._last_update_time[symbol] = datetime.now(timezone.utc)

            return df

        except Exception as e:
            logger.error(f"Error actualizando vela para {symbol}: {e}")
            return self.candles.get(symbol, pd.DataFrame())

    def get_price_changue_percent(self, symbol: str):
        return self.rest_client.get_price_change_percent(symbol=symbol)

    def get_candles(self, symbol: str) -> Optional[pd.DataFrame]:
        """Obtiene el DataFrame de velas para un símbolo."""
        return self.candles.get(symbol)

    def get_latest_candle(self, symbol: str) -> Optional[pd.Series]:
        """Obtiene la última vela de un símbolo."""
        df = self.candles.get(symbol)
        if df is not None and len(df) > 0:
            return df.iloc[-1]
        return None

    def get_symbols(self) -> List[str]:
        """Retorna lista de símbolos cargados."""
        return list(self.candles.keys())

    def _convert_to_dataframe(self, data: List) -> pd.DataFrame:
        """
        Convierte datos crudos de API a DataFrame estándar.

        Formato esperado (de BinanceRESTClient):
        [symbol, open_time, close_time, open, close, high, low, volume]
        """
        if not data:
            return pd.DataFrame()

        # Verificar si son listas o dicts
        if isinstance(data[0], (list, tuple)):
            # Formato lista
            df = pd.DataFrame(data, columns=[
                "symbol", "open_time", "close_time", "open", "close", "high", "low", "volume"
            ])
        elif isinstance(data[0], dict):
            # Formato dict
            df = pd.DataFrame(data)
        else:
            logger.warning(f"Formato de datos no reconocido: {type(data[0])}")
            return pd.DataFrame()

        # Normalizar nombres de columnas
        df = self._normalize_columns(df)

        # Convertir tipos
        df = self._convert_types(df)

        return df.reset_index(drop=True)

    def _parse_kline_data(self, kline_data) -> Optional[Dict]:
        """
        Parsea datos de vela de WebSocket a formato estándar.

        Soporta:
        - Lista/Tupla: [symbol, open_time, close_time, open, close, high, low, volume]
        - Diccionario con claves variadas
        """
        candle = {}

        try:
            # Formato LISTA
            if isinstance(kline_data, (list, tuple)):
                if len(kline_data) >= 8:
                    candle = {
                        "symbol": str(kline_data[0]),
                        "open_time": int(kline_data[1]),
                        "close_time": int(kline_data[2]),
                        "open": float(kline_data[3]),
                        "close": float(kline_data[4]),
                        "high": float(kline_data[5]),
                        "low": float(kline_data[6]),
                        "volume": float(kline_data[7]),
                    }
                else:
                    logger.error(f"Lista incompleta: len={len(kline_data)}")
                    return None

            # Formato DICCIONARIO
            elif isinstance(kline_data, dict):
                # Mapear claves alternativas
                candle = {
                    "symbol": kline_data.get("symbol", kline_data.get("s")),
                    "open_time": int(kline_data.get("open_time", kline_data.get("t", kline_data.get("openTime", 0)))),
                    "close_time": int(kline_data.get("close_time", kline_data.get("T", kline_data.get("closeTime", 0)))),
                    "open": float(kline_data.get("open", kline_data.get("o", kline_data.get("openPrice", 0)))),
                    "close": float(kline_data.get("close", kline_data.get("c", kline_data.get("closePrice", 0)))),
                    "high": float(kline_data.get("high", kline_data.get("h", kline_data.get("highPrice", 0)))),
                    "low": float(kline_data.get("low", kline_data.get("l", kline_data.get("lowPrice", 0)))),
                    "volume": float(kline_data.get("volume", kline_data.get("v", kline_data.get("baseVolume", 0)))),
                }
            else:
                logger.error(f"Formato no soportado: {type(kline_data)}")
                return None

            # Validar valores críticos
            if candle.get("close", 0) <= 0 or candle.get("close_time", 0) == 0:
                logger.warning(f"Vela inválida: {candle}")
                return None

            return candle

        except Exception as e:
            logger.error(f"Error parseando kline: {e}")
            return None

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nombres de columnas a formato estándar."""
        column_map = {
            "s": "symbol",
            "t": "open_time",
            "T": "close_time",
            "o": "open",
            "c": "close",
            "h": "high",
            "l": "low",
            "v": "volume",
            "openTime": "open_time",
            "closeTime": "close_time",
            "openPrice": "open",
            "closePrice": "close",
            "highPrice": "high",
            "lowPrice": "low",
        }

        return df.rename(columns=column_map)

    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convierte tipos de columnas a formatos apropiados."""
        type_map = {
            "open_time": "int64",
            "close_time": "int64",
            "open": "float64",
            "close": "float64",
            "high": "float64",
            "low": "float64",
            "volume": "float64",
        }

        for col, dtype_str in type_map.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype_str)
                except Exception as e:
                    logger.warning(f"No se pudo convertir {col} a {dtype_str}: {e}")

        return df

    def _convert_interval_format(self, interval: str) -> str:
        """
        Convierte formato de intervalo a formato Binance si es necesario.

        Ejemplos:
        - "1m" -> "1m"
        - "5m" -> "5m"
        - "1h" -> "1h"
        - "1d" -> "1d"
        """
        # Ya está en formato correcto
        return interval

    def clear(self, symbol: Optional[str] = None):
        """
        Limpia datos almacenados.

        Args:
            symbol: Si se especifica, limpia solo ese símbolo. Si es None, limpia todo.
        """
        if symbol:
            self.candles.pop(symbol, None)
            self._last_update_time.pop(symbol, None)
            logger.info(f"Datos de {symbol} limpiados")
        else:
            self.candles.clear()
            self._last_update_time.clear()
            logger.info("Todos los datos limpiados")

