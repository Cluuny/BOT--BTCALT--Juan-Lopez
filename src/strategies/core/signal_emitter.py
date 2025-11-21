"""
Emisor estandarizado de señales de trading.
Maneja validación y envío de señales a través de colas asyncio.
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timezone
from utils.logger import Logger
from contracts.signal_contract import ValidatedSignal

logger = Logger.get_logger(__name__)


class SignalEmitter:
    """
    Emisor de señales de trading con validación automática.

    Características:
    - Validación de datos antes de emitir
    - Construcción automática de ValidatedSignal
    - Manejo de colas asyncio
    - Logging detallado
    - Rate limiting opcional
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        run_db_id: Optional[int] = None,
        min_signal_interval: float = 0.0,  # Segundos entre señales del mismo símbolo
    ):
        """
        Args:
            signal_queue: Cola asyncio donde enviar señales
            bot_id: ID del bot que genera señales
            run_db_id: ID de la ejecución actual (para persistencia)
            min_signal_interval: Tiempo mínimo entre señales del mismo símbolo
        """
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id
        self.min_signal_interval = min_signal_interval

        # Rate limiting
        self._last_signal_time: Dict[str, datetime] = {}

    async def emit_signal(
        self,
        symbol: str,
        signal_type: str,
        price: float,
        reason: str,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> bool:
        """
        Emite una señal de trading.

        Args:
            symbol: Símbolo (ej: "BTCUSDT")
            signal_type: "BUY", "SELL", "CLOSE", etc.
            price: Precio al que se genera la señal
            reason: Descripción del motivo de la señal
            indicator_snapshot: Diccionario con valores de indicadores
            metadata: Metadatos adicionales
            force: Si True, ignora rate limiting

        Returns:
            True si la señal fue emitida, False si fue bloqueada
        """
        # Rate limiting
        if not force and self.min_signal_interval > 0:
            last_time = self._last_signal_time.get(symbol)
            if last_time:
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
                if elapsed < self.min_signal_interval:
                    logger.debug(
                        f"Señal para {symbol} bloqueada por rate limit "
                        f"({elapsed:.1f}s < {self.min_signal_interval}s)"
                    )
                    return False

        # Validar datos críticos
        if not self._validate_signal_data(symbol, signal_type, price, indicator_snapshot):
            return False

        # Construir señal
        try:
            signal = self._build_signal(
                symbol=symbol,
                signal_type=signal_type,
                price=price,
                reason=reason,
                indicator_snapshot=indicator_snapshot or {},
                metadata=metadata or {},
            )

            # Enviar a cola
            await self.signal_queue.put(signal)

            # Actualizar timestamp
            self._last_signal_time[symbol] = datetime.now(timezone.utc)

            # Log
            indicator_str = self._format_indicators(indicator_snapshot)
            logger.info(
                f"🔔 SEÑAL EMITIDA: {signal_type} {symbol} @ {price:.4f} | "
                f"Razón: {reason} | {indicator_str}"
            )

            return True

        except Exception as e:
            logger.error(f"Error emitiendo señal: {e}")
            return False

    async def emit_buy(
        self,
        symbol: str,
        price: float,
        reason: str,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atajo para emitir señal BUY."""
        return await self.emit_signal(
            symbol=symbol,
            signal_type="BUY",
            price=price,
            reason=reason,
            indicator_snapshot=indicator_snapshot,
            metadata=metadata,
        )

    async def emit_sell(
        self,
        symbol: str,
        price: float,
        reason: str,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atajo para emitir señal SELL."""
        return await self.emit_signal(
            symbol=symbol,
            signal_type="SELL",
            price=price,
            reason=reason,
            indicator_snapshot=indicator_snapshot,
            metadata=metadata,
        )

    async def emit_close(
        self,
        symbol: str,
        price: float,
        reason: str,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Atajo para emitir señal CLOSE."""
        return await self.emit_signal(
            symbol=symbol,
            signal_type="CLOSE",
            price=price,
            reason=reason,
            indicator_snapshot=indicator_snapshot,
            metadata=metadata,
        )

    def _validate_signal_data(
        self,
        symbol: str,
        signal_type: str,
        price: float,
        indicator_snapshot: Optional[Dict[str, Any]],
    ) -> bool:
        """Valida datos de señal antes de emitir."""

        # Validar símbolo
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Símbolo inválido: {symbol}")
            return False

        # Validar tipo de señal
        valid_types = ["BUY", "SELL", "CLOSE", "LONG", "SHORT"]
        if signal_type not in valid_types:
            logger.error(f"Tipo de señal inválido: {signal_type}")
            return False

        # Validar precio
        if not isinstance(price, (int, float)) or price <= 0:
            logger.error(f"Precio inválido: {price}")
            return False

        # Validar indicadores críticos (ej: RSI no puede ser None para estrategias RSI)
        if indicator_snapshot:
            for key, value in indicator_snapshot.items():
                if value is None:
                    logger.warning(f"Indicador {key} es None en snapshot")
                elif not isinstance(value, (int, float, str, bool)):
                    logger.warning(f"Indicador {key} tiene tipo inválido: {type(value)}")

        return True

    def _build_signal(
        self,
        symbol: str,
        signal_type: str,
        price: float,
        reason: str,
        indicator_snapshot: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Construye objeto de señal."""

        # Preparar datos de señal en formato simple
        signal_data = {
            "symbol": symbol,
            "type": signal_type,  # "type" en lugar de "signal_type" para compatibilidad
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "bot_id": self.bot_id,
            "run_db_id": self.run_db_id,
            "indicators": indicator_snapshot,
            "metadata": metadata,
            "risk_params": {"position_size": 0.1},  # Default risk params
        }

        # ⚠️ IMPORTANTE: Si position_size_usdt está en metadata, moverlo al nivel superior
        # donde el validador lo espera
        if "position_size_usdt" in metadata:
            signal_data["position_size_usdt"] = metadata["position_size_usdt"]
            logger.debug(f"position_size_usdt extraído de metadata: {metadata['position_size_usdt']}")

        # Añadir RSI si está presente (para compatibilidad con contratos existentes)
        if "RSI" in indicator_snapshot:
            signal_data["rsi"] = indicator_snapshot["RSI"]

        return signal_data

    def _format_indicators(self, indicator_snapshot: Optional[Dict[str, Any]]) -> str:
        """Formatea indicadores para logging."""
        if not indicator_snapshot:
            return ""

        # Filtrar valores None y formatear
        formatted = []
        for key, value in indicator_snapshot.items():
            if value is None:
                continue

            if isinstance(value, float):
                formatted.append(f"{key}={value:.4f}")
            elif isinstance(value, int):
                formatted.append(f"{key}={value}")
            else:
                formatted.append(f"{key}={value}")

        return " | ".join(formatted[:5])  # Limitar a 5 indicadores para no saturar logs

    def get_last_signal_time(self, symbol: str) -> Optional[datetime]:
        """Obtiene el timestamp de la última señal emitida para un símbolo."""
        return self._last_signal_time.get(symbol)

    def reset_rate_limit(self, symbol: Optional[str] = None):
        """
        Resetea el rate limiting.

        Args:
            symbol: Si se especifica, resetea solo ese símbolo. Si es None, resetea todo.
        """
        if symbol:
            self._last_signal_time.pop(symbol, None)
        else:
            self._last_signal_time.clear()


class SignalValidator:
    """
    Validador adicional de señales con reglas personalizables.
    Útil para filtros más complejos antes de emitir.
    """

    @staticmethod
    def validate_rsi_signal(
        signal_type: str,
        rsi: Optional[float],
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> bool:
        """Valida señal basada en RSI."""
        if rsi is None:
            return False

        if signal_type == "BUY" and rsi > oversold:
            logger.debug(f"BUY bloqueada: RSI {rsi:.2f} > {oversold}")
            return False

        if signal_type == "SELL" and rsi < overbought:
            logger.debug(f"SELL bloqueada: RSI {rsi:.2f} < {overbought}")
            return False

        return True

    @staticmethod
    def validate_volume(
        current_volume: float,
        avg_volume: float,
        min_ratio: float = 1.2,
    ) -> bool:
        """Valida que el volumen sea suficiente."""
        if avg_volume <= 0:
            return True  # No podemos validar

        ratio = current_volume / avg_volume
        if ratio < min_ratio:
            logger.debug(f"Volumen insuficiente: {ratio:.2f}x < {min_ratio}x")
            return False

        return True

    @staticmethod
    def validate_price_change(
        current_price: float,
        reference_price: float,
        min_change_pct: float = 0.1,
    ) -> bool:
        """Valida que el cambio de precio sea significativo."""
        change_pct = abs((current_price - reference_price) / reference_price * 100)

        if change_pct < min_change_pct:
            logger.debug(f"Cambio de precio insignificante: {change_pct:.3f}%")
            return False

        return True

