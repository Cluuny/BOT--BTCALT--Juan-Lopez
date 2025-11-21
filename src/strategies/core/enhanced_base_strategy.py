"""
Base Strategy mejorada con componentes modulares.
Simplifica enormemente la creación de nuevas estrategias.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import asyncio
import pandas as pd
from dataclasses import dataclass

from utils.logger import Logger
from data.rest_data_provider import BinanceRESTClient
from data.ws_BSM_provider import RealTimeDataCollector

from strategies.core.data_manager import DataManager
from strategies.core.indicator_calculator import IndicatorCalculator
from strategies.core.signal_emitter import SignalEmitter

logger = Logger.get_logger(__name__)


@dataclass
class RiskParameters:
    """
    Parámetros de riesgo para gestión de posiciones.

    Attributes:
        position_size: Fracción del balance a usar (0.0-1.0), ej: 0.1 = 10%
        max_open_positions: Máximo número de posiciones abiertas simultáneas
        stop_loss_pct: Porcentaje de stop loss (opcional)
        take_profit_pct: Porcentaje de take profit (opcional)
    """
    position_size: float = 0.1  # 10% por defecto
    max_open_positions: int = 5
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


class EnhancedBaseStrategy(ABC):
    # Clase interna para compatibilidad con código existente
    RiskParameters = RiskParameters
    """
    Estrategia base mejorada con componentes modulares.

    Flujo simplificado:
    1. Configurar indicadores en setup_indicators()
    2. Definir condiciones de entrada/salida en check_conditions()
    3. El resto se maneja automáticamente

    Ejemplo de uso:
        class MyStrategy(EnhancedBaseStrategy):
            def setup_indicators(self):
                self.indicators.add_rsi(14)
                self.indicators.add_sma(50)

            async def check_conditions(self, symbol, candle, indicators):
                rsi = indicators.get('RSI')
                sma = indicators.get('SMA50')

                if candle['close'] < sma and rsi < 30:
                    await self.emit_buy(symbol, candle['close'], "RSI oversold + below SMA50")
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: List[str],
        timeframe: str = "1m",
        run_db_id: Optional[int] = None,
        rest_client: Optional[BinanceRESTClient] = None,
        confirmation_queue: Optional[asyncio.Queue] = None,
        historical_candles: int = 100,
    ):
        """
        Args:
            signal_queue: Cola para enviar señales
            bot_id: ID del bot
            symbols: Lista de símbolos a operar
            timeframe: Intervalo de velas (1m, 5m, 1h, etc.)
            run_db_id: ID de ejecución para DB
            rest_client: Cliente REST de Binance
            confirmation_queue: Cola para recibir confirmaciones
            historical_candles: Cantidad de velas históricas a cargar
        """
        self.symbols = symbols
        self.timeframe = timeframe
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        self.signal_queue = signal_queue
        self.confirmation_queue = confirmation_queue
        self.historical_candles = historical_candles

        # Componentes core
        self.rest_client = rest_client or BinanceRESTClient()
        self.data_manager = DataManager(
            rest_client=self.rest_client,
            max_candles_per_symbol=max(historical_candles, 200),
            default_interval=timeframe,
        )
        self.indicators = IndicatorCalculator()
        self.signal_emitter = SignalEmitter(
            signal_queue=signal_queue,
            bot_id=bot_id,
            run_db_id=run_db_id,
        )

        # Estado interno
        self._initialized = False
        self._ws_collector: Optional[RealTimeDataCollector] = None

    # ==================== MÉTODOS ABSTRACTOS (IMPLEMENTAR EN SUBCLASES) ====================

    @abstractmethod
    def setup_indicators(self):
        """
        Configura los indicadores a calcular.

        Ejemplo:
            self.indicators.add_rsi(14)
            self.indicators.add_bbands(20, 2.0)
            self.indicators.add_sma(50)
        """
        pass

    @abstractmethod
    async def check_conditions(
        self,
        symbol: str,
        candle: pd.Series,
        indicators: Dict[str, float],
    ):
        """
        Evalúa condiciones de trading y emite señales.

        Args:
            symbol: Símbolo actual
            candle: Serie con datos OHLCV de la última vela
            indicators: Dict con valores de indicadores calculados

        Ejemplo:
            rsi = indicators.get('RSI')
            if rsi < 30:
                await self.emit_buy(symbol, candle['close'], "RSI oversold")
        """
        pass

    # ==================== CICLO DE VIDA ====================

    async def start(self):
        """Inicia la estrategia."""
        logger.info(f"Iniciando estrategia mejorada para {len(self.symbols)} símbolos...")

        try:
            # 1. Configurar indicadores
            self.setup_indicators()
            logger.info(f"Indicadores configurados: {self.indicators.get_indicator_names()}")

            # 2. Cargar datos históricos
            min_candles = max(
                self.indicators.get_min_required_rows() + 5,
                self.historical_candles
            )
            await self.data_manager.load_historical_data(
                symbols=self.symbols,
                interval=self.timeframe,
                limit=min_candles,
            )

            # 3. Calcular indicadores iniciales
            await self._compute_all_indicators()

            # 4. Hooks personalizados
            await self.on_start()

            self._initialized = True
            logger.info("✅ Estrategia inicializada correctamente")

            # 5. Iniciar WebSocket
            await self._start_websocket()

        except Exception as e:
            logger.error(f"Error iniciando estrategia: {e}")
            raise

    async def _start_websocket(self):
        """Inicia el recolector de datos en tiempo real."""
        try:
            self._ws_collector = RealTimeDataCollector(
                symbols=self.symbols,
                interval=self.timeframe,
                on_update=self._handle_websocket_update,
            )

            await self._ws_collector.start()
            logger.info("WebSocket iniciado correctamente")

        except Exception as e:
            logger.error(f"Error iniciando WebSocket: {e}")
            raise

    async def _handle_websocket_update(self, last_candles: Dict):
        """Maneja actualizaciones de velas desde WebSocket."""
        if not self._initialized:
            logger.warning("Estrategia no inicializada, ignorando update")
            return

        for symbol, kline_data in last_candles.items():
            try:
                # 1. Actualizar datos
                df = self.data_manager.update_candle(symbol, kline_data)

                if len(df) == 0:
                    logger.warning(f"DataFrame vacío para {symbol}")
                    continue

                # 2. Calcular indicadores
                df_with_indicators = self.indicators.compute(df)
                self.data_manager.candles[symbol] = df_with_indicators

                # 3. Extraer última vela
                last_candle = df_with_indicators.iloc[-1]

                # 4. Preparar dict de indicadores
                indicator_values = self._extract_indicators(last_candle)

                # 5. Log estado
                self._log_candle_update(symbol, last_candle, indicator_values)

                # 6. Evaluar condiciones (método abstracto)
                await self.check_conditions(symbol, last_candle, indicator_values)

                # 7. Hook personalizado
                await self.on_candle_update(symbol, last_candle, indicator_values)

            except Exception as e:
                logger.error(f"Error procesando update de {symbol}: {e}")

    # ==================== MÉTODOS DE AYUDA ====================

    async def emit_buy(
        self,
        symbol: str,
        price: float,
        reason: str,
        metadata: Optional[Dict] = None,
    ):
        """Emite señal BUY."""
        candle = self.data_manager.get_latest_candle(symbol)
        indicators = self._extract_indicators(candle) if candle is not None else {}

        await self.signal_emitter.emit_buy(
            symbol=symbol,
            price=price,
            reason=reason,
            indicator_snapshot=indicators,
            metadata=metadata,
        )

    async def emit_sell(
        self,
        symbol: str,
        price: float,
        reason: str,
        metadata: Optional[Dict] = None,
    ):
        """Emite señal SELL."""
        candle = self.data_manager.get_latest_candle(symbol)
        indicators = self._extract_indicators(candle) if candle is not None else {}

        await self.signal_emitter.emit_sell(
            symbol=symbol,
            price=price,
            reason=reason,
            indicator_snapshot=indicators,
            metadata=metadata,
        )

    async def emit_close(
        self,
        symbol: str,
        price: float,
        reason: str,
        metadata: Optional[Dict] = None,
    ):
        """Emite señal CLOSE."""
        candle = self.data_manager.get_latest_candle(symbol)
        indicators = self._extract_indicators(candle) if candle is not None else {}

        await self.signal_emitter.emit_close(
            symbol=symbol,
            price=price,
            reason=reason,
            indicator_snapshot=indicators,
            metadata=metadata,
        )

    def get_candles(self, symbol: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Obtiene DataFrame de velas para un símbolo."""
        df = self.data_manager.get_candles(symbol)
        if df is None:
            return pd.DataFrame()

        if limit:
            return df.tail(limit)

        return df

    def get_indicator_value(self, symbol: str, indicator_name: str) -> Optional[float]:
        """Obtiene el último valor de un indicador específico."""
        candle = self.data_manager.get_latest_candle(symbol)
        if candle is None:
            return None

        return candle.get(indicator_name)

    # ==================== MÉTODOS PRIVADOS ====================

    async def _compute_all_indicators(self):
        """Calcula indicadores para todos los símbolos."""
        for symbol in self.symbols:
            df = self.data_manager.get_candles(symbol)
            if df is not None and len(df) > 0:
                df_with_indicators = self.indicators.compute(df)
                self.data_manager.candles[symbol] = df_with_indicators
                logger.debug(f"{symbol}: Indicadores calculados")

    def _extract_indicators(self, candle: pd.Series) -> Dict[str, float]:
        """Extrae valores de indicadores de una vela."""
        indicators = {}

        # Obtener nombres de indicadores configurados
        indicator_names = self.indicators.get_indicator_names()

        # También incluir columnas comunes de Bollinger Bands y MACD
        extra_columns = ['BBL', 'BBM', 'BBU', 'MACD', 'MACD_signal', 'MACD_hist']
        all_columns = indicator_names + extra_columns

        for col in all_columns:
            if col in candle.index:
                value = candle[col]
                # Solo incluir si no es None/NaN
                if pd.notna(value):
                    indicators[col] = float(value)

        # Agregar precio y volumen actuales
        if 'close' in candle.index:
            indicators['close'] = float(candle['close'])
        if 'volume' in candle.index:
            indicators['volume'] = float(candle['volume'])

        return indicators

    def _log_candle_update(self, symbol: str, candle: pd.Series, indicators: Dict):
        """Log de actualización de vela."""
        close = candle.get('close', 0)

        # Formatear indicadores más relevantes
        relevant = []
        for key in ['RSI', 'SMA50', 'EMA21', 'BBL', 'BBU', 'MACD']:
            if key in indicators:
                relevant.append(f"{key}={indicators[key]:.2f}")

        indicator_str = " | ".join(relevant[:4])  # Limitar para no saturar logs

        logger.info(f"{symbol} actualizado: close={close:.4f} | {indicator_str}")

    # ==================== HOOKS OPCIONALES ====================

    async def on_start(self):
        """Hook llamado después de inicializar. Override si necesitas lógica custom."""
        pass

    async def on_candle_update(
        self,
        symbol: str,
        candle: pd.Series,
        indicators: Dict[str, float],
    ):
        """Hook llamado después de cada actualización. Override para lógica adicional."""
        pass

    async def on_stop(self):
        """Hook llamado al detener la estrategia. Override para limpieza."""
        pass

    # ==================== MÉTODOS DE COMPATIBILIDAD CON BaseStrategy ====================

    def _request_for_init(self, symbols: List[str]):
        """Compatibilidad con BaseStrategy antiguo."""
        # Ya no se usa, la inicialización es async
        pass

    async def _handle_update(self, last_candles: dict):
        """Compatibilidad con BaseStrategy antiguo."""
        await self._handle_websocket_update(last_candles)

