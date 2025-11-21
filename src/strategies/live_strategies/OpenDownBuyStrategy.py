"""
Estrategia basada en el precio de apertura diario.
MIGRADA al framework EnhancedBaseStrategy.

Señales:
  - BUY cuando el precio cae X% desde la apertura diaria
  - SELL cuando el precio sube Y% desde la apertura diaria (en posición abierta)
"""

import asyncio
from typing import Dict, Optional
import pandas as pd
from datetime import datetime, timezone

from strategies.core import EnhancedBaseStrategy
from utils.logger import Logger

logger = Logger.get_logger(__name__)


class OpenDownBuyStrategy(EnhancedBaseStrategy):
    """
    Estrategia de compra en caídas desde apertura diaria.
    Mejorada con framework modular.
    """

    def __init__(
        self,
        signal_queue: asyncio.Queue,
        bot_id: int,
        symbols: list[str],
        timeframe: str = "1m",
        run_db_id: int | None = None,
        # Parámetros específicos de la estrategia
        entry_threshold: float = -1.0,  # % de caída para entrar
        exit_threshold: float = 2.0,  # % de subida para salir
        position_size_percent: float = 100.0,
        base_capital: float = 10.0,
        **kwargs
    ):
        # Esta estrategia solo maneja UN símbolo
        if len(symbols) > 1:
            logger.warning(f"OpenDownBuyStrategy solo maneja un símbolo. Usando: {symbols[0]}")
            symbols = [symbols[0]]

        # Filtrar kwargs para no pasar parámetros desconocidos a EnhancedBaseStrategy
        base_kwargs = {
            'rest_client': kwargs.get('rest_client'),
            'confirmation_queue': kwargs.get('confirmation_queue'),
            'historical_candles': 10,  # Solo necesitamos datos básicos
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

        self.symbol = symbols[0]
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size_percent = position_size_percent
        self.base_capital = base_capital

        # Estado de la estrategia
        self.daily_open_price: Optional[float] = None
        self.daily_open_time: Optional[datetime] = None
        self.last_open_check_date: Optional[datetime] = None

        # Control de posiciones - SOLO UNA COMPRA POR DÍA
        self.open_positions: list[Dict] = []  # Lista de posiciones abiertas
        self.has_bought_today: bool = False  # Flag para controlar compra diaria
        self.current_open_price_id: Optional[str] = None  # ID único del precio de apertura actual

        # Notificaciones
        self.last_pnl_notification: Optional[datetime] = None

    def setup_indicators(self):
        """
        Esta estrategia no usa indicadores técnicos tradicionales.
        Se basa en el cambio porcentual desde la apertura diaria.
        """
        # No se requieren indicadores
        pass

    async def check_conditions(
        self,
        symbol: str,
        candle: pd.Series,
        indicators: Dict[str, float]
    ):
        """
        Evalúa condiciones de entrada y salida basadas en cambio % desde apertura.
        """
        try:
            current_price = candle['close']
            current_time = datetime.now(timezone.utc)

            # Validar que tenemos precio de apertura
            if self.daily_open_price is None or self.daily_open_price <= 0:
                logger.debug("Precio de apertura no disponible aún")
                # Intentar inicializarlo con el precio actual
                await self._initialize_daily_open(current_price, current_time)
                return

            # Verificar si cambió el día
            await self._check_and_update_daily_open(current_time)

            # Calcular cambio porcentual desde apertura
            price_change_pct = (
                (current_price - self.daily_open_price) / self.daily_open_price
            ) * 100

            # Log de estado
            logger.info(
                f"{symbol} | Precio: {current_price:.2f} | "
                f"Apertura: {self.daily_open_price:.2f} | "
                f"Cambio: {price_change_pct:+.2f}% | "
                f"Posiciones: {len(self.open_positions)} | "
                f"Compró hoy: {'SÍ' if self.has_bought_today else 'NO'}"
            )

            # =====================================================
            # LÓGICA DE TRADING - UNA COMPRA POR DÍA
            # =====================================================
            # Solo verificar entrada si NO ha comprado hoy
            if not self.has_bought_today:
                await self._check_entry_condition(
                    current_price, price_change_pct, current_time
                )
            else:
                logger.debug(f"⏸️ Ya se compró hoy para este precio de apertura, esperando próximo día")

            # Verificar salida para cada posición abierta
            if len(self.open_positions) > 0:
                await self._check_exit_conditions_for_all_positions(
                    current_price, price_change_pct, current_time
                )
                await self._notify_pnl(current_price, current_time)

        except Exception as e:
            logger.error(f"Error en check_conditions para {symbol}: {e}")

    async def _initialize_daily_open(self, current_price: float, current_time: datetime):
        """Inicializa el precio de apertura diaria."""
        try:
            # Intentar obtener datos diarios
            df_daily = await self.data_manager.load_historical_data(
                symbols=[self.symbol],
                interval="1d",
                limit=1,
            )

            if self.symbol in self.data_manager.candles:
                df = self.data_manager.candles[self.symbol]
                if len(df) > 0:
                    last_daily = df.iloc[-1]
                    self.daily_open_price = float(last_daily['open'])

                    # Obtener timestamp si está disponible
                    if 'open_time' in last_daily:
                        self.daily_open_time = datetime.fromtimestamp(
                            int(last_daily['open_time']) / 1000, tz=timezone.utc
                        )
                else:
                    self.daily_open_time = current_time

                self.last_open_check_date = self.daily_open_time.date()

                # Generar ID único para este precio de apertura
                self.current_open_price_id = f"{self.daily_open_time.strftime('%Y%m%d')}_{self.daily_open_price}"
                self.has_bought_today = False  # Resetear flag

                logger.info("=" * 60)
                logger.info("PRECIO DE APERTURA DIARIO CARGADO")
                logger.info(f"   Precio: {self.daily_open_price:.2f} USDT")
                logger.info(f"   Fecha: {self.daily_open_time.strftime('%Y-%m-%d %H:%M UTC')}")
                logger.info(f"   ID Apertura: {self.current_open_price_id}")
                logger.info("=" * 60)
                return

            # Fallback: usar cambio porcentual dado por Binance para calcular apertura
            logger.warning("No se pudo cargar apertura diaria desde API, usando cambio % de Binance")
            try:
                change_percent = self.data_manager.get_price_changue_percent(self.symbol)
                if change_percent is not None:
                    # Calcular precio de apertura basado en el cambio porcentual
                    # Formula: open_price = current_price / (1 + change_percent/100)
                    self.daily_open_price = current_price / (1 + change_percent / 100.0)
                    self.daily_open_time = current_time
                    self.last_open_check_date = current_time.date()

                    # Generar ID único para este precio de apertura
                    self.current_open_price_id = f"{self.daily_open_time.strftime('%Y%m%d')}_{self.daily_open_price}"
                    self.has_bought_today = False  # Resetear flag

                    logger.info("="*60)
                    logger.info("PRECIO DE APERTURA CALCULADO DESDE CAMBIO %")
                    logger.info(f"   Cambio 24h: {change_percent:+.2f}%")
                    logger.info(f"   Precio Actual: {current_price:.2f} USDT")
                    logger.info(f"   Precio Apertura: {self.daily_open_price:.2f} USDT")
                    logger.info(f"   Fecha: {self.daily_open_time.strftime('%Y-%m-%d %H:%M UTC')}")
                    logger.info(f"   ID Apertura: {self.current_open_price_id}")
                    logger.info("="*60)
                else:
                    # Si también falla, usar precio actual como fallback
                    logger.error("No se pudo obtener cambio porcentual, usando precio actual")
                    self.daily_open_price = current_price
                    self.daily_open_time = current_time
                    self.last_open_check_date = current_time.date()
            except Exception as e:
                logger.error(f"Error obteniendo cambio porcentual: {e}")
                self.daily_open_price = current_price
                self.daily_open_time = current_time
                self.last_open_check_date = current_time.date()

        except Exception as e:
            logger.error(f"Error inicializando apertura diaria: {e}")
            # Fallback final
            self.daily_open_price = current_price
            self.daily_open_time = current_time
            self.last_open_check_date = current_time.date()

    async def _check_and_update_daily_open(self, current_time: datetime):
        """Actualiza el precio de apertura si cambió el día."""
        try:
            current_date = current_time.date()

            # Solo actualizar si es nuevo día Y no hay posiciones activas
            if (
                self.last_open_check_date == current_date
                or len(self.open_positions) > 0
                or self.daily_open_time is None
            ):
                return

            logger.info(f"Nuevo día detectado ({current_date}). Actualizando apertura...")

            # Cargar nueva vela diaria
            await self.data_manager.load_historical_data(
                symbols=[self.symbol],
                interval="1d",
                limit=1,
            )

            if self.symbol in self.data_manager.candles:
                df = self.data_manager.candles[self.symbol]
                if len(df) > 0:
                    new_daily = df.iloc[-1]
                    new_open_price = float(new_daily['open'])

                    if 'open_time' in new_daily:
                        new_open_time = datetime.fromtimestamp(
                            int(new_daily['open_time']) / 1000, tz=timezone.utc
                        )

                        # Solo actualizar si es del día correcto
                        if new_open_time.date() == current_date:
                            old_open = self.daily_open_price
                            old_id = self.current_open_price_id

                            self.daily_open_price = new_open_price
                            self.daily_open_time = new_open_time

                            # Generar nuevo ID y resetear flag de compra
                            self.current_open_price_id = f"{new_open_time.strftime('%Y%m%d')}_{new_open_price}"
                            self.has_bought_today = False  # ⚠️ IMPORTANTE: Permite nueva compra para el nuevo día

                            logger.info("="*60)
                            logger.info("🔄 NUEVO PRECIO DE APERTURA DIARIO")
                            logger.info(f"   Apertura anterior: {old_open:.2f} USDT (ID: {old_id})")
                            logger.info(f"   Apertura nueva: {new_open_price:.2f} USDT (ID: {self.current_open_price_id})")
                            logger.info(f"   Fecha: {new_open_time.strftime('%Y-%m-%d %H:%M UTC')}")
                            logger.info(f"   ✅ Flag 'has_bought_today' reseteado - Se permite nueva compra")
                            logger.info("="*60)

            self.last_open_check_date = current_date

        except Exception as e:
            logger.error(f"Error actualizando apertura diaria: {e}")
            self.last_open_check_date = current_time.date()

    async def _check_entry_condition(
        self, price: float, change_pct: float, current_time: datetime
    ):
        """Verifica condición de entrada (solo UNA compra por día)."""
        if change_pct <= self.entry_threshold:
            logger.info(
                f"✅ CONDICIÓN DE ENTRADA: {change_pct:.2f}% <= {self.entry_threshold}%"
            )

            position_size_usdt = self.base_capital * (self.position_size_percent / 100.0)

            reason = (
                f"Caída del {change_pct:.2f}% desde apertura "
                f"({self.daily_open_price:.2f} USDT)"
            )

            # Emitir señal usando el framework
            await self.emit_buy(
                symbol=self.symbol,
                price=price,
                reason=reason,
                metadata={
                    'strategy': 'OpenDownBuy',
                    'daily_open_price': self.daily_open_price,
                    'change_pct': change_pct,
                    'entry_threshold': self.entry_threshold,
                    'position_size_usdt': position_size_usdt,
                    'open_price_id': self.current_open_price_id,
                }
            )

            # Esperar confirmación si está disponible
            if self.confirmation_queue is not None:
                confirmed = await self._wait_for_confirmation()

                if confirmed:
                    # Agregar nueva posición y marcar que ya se compró hoy
                    position = {
                        'entry_price': price,
                        'entry_time': current_time,
                        'entry_qty': position_size_usdt / price,
                        'entry_change_pct': change_pct,
                        'open_price_id': self.current_open_price_id,
                    }
                    self.open_positions.append(position)
                    self.has_bought_today = True  # ⚠️ IMPORTANTE: Bloquea nuevas compras hasta mañana

                    logger.info("="*60)
                    logger.info(f"✅ POSICIÓN ABIERTA: {self.symbol} @ {price:.2f}")
                    logger.info(f"   Cambio desde apertura: {change_pct:.2f}%")
                    logger.info(f"   ID Apertura: {self.current_open_price_id}")
                    logger.info(f"   🔒 Flag 'has_bought_today' = True")
                    logger.info(f"   ⏸️  No se comprará más hasta el próximo precio de apertura")
                    logger.info("="*60)
                else:
                    logger.warning("⚠️ Orden no confirmada - NO se marca has_bought_today")
            else:
                # Sin cola de confirmación, asumir apertura
                position = {
                    'entry_price': price,
                    'entry_time': current_time,
                    'entry_qty': position_size_usdt / price,
                    'entry_change_pct': change_pct,
                    'open_price_id': self.current_open_price_id,
                }
                self.open_positions.append(position)
                self.has_bought_today = True  # ⚠️ IMPORTANTE: Bloquea nuevas compras

                logger.info("="*60)
                logger.info(f"✅ POSICIÓN ABIERTA: {self.symbol} @ {price:.2f}")
                logger.info(f"   (Sin confirmación de TradeEngine)")
                logger.info(f"   🔒 Flag 'has_bought_today' = True")
                logger.info("="*60)

    async def _check_exit_conditions_for_all_positions(
        self, price: float, change_pct: float, current_time: datetime
    ):
        """Verifica condición de salida para todas las posiciones abiertas."""
        if change_pct >= self.exit_threshold:
            logger.info(
                f"✅ CONDICIÓN DE SALIDA: {change_pct:.2f}% >= {self.exit_threshold}%"
            )

            # Cerrar todas las posiciones abiertas
            positions_to_close = self.open_positions.copy()
            self.open_positions.clear()

            for idx, position in enumerate(positions_to_close, 1):
                entry_price = position['entry_price']
                entry_time = position['entry_time']

                # Calcular PnL
                if entry_price and entry_price > 0:
                    pnl_pct = ((price - entry_price) / entry_price) * 100
                    pnl_usdt = self.base_capital * (pnl_pct / 100.0)
                else:
                    pnl_pct = 0.0
                    pnl_usdt = 0.0

                reason = (
                    f"Recuperación {change_pct:.2f}% desde apertura | "
                    f"PnL: {pnl_pct:.2f}% ({pnl_usdt:+.2f} USDT)"
                )

                # Emitir señal de salida
                await self.emit_sell(
                    symbol=self.symbol,
                    price=price,
                    reason=reason,
                    metadata={
                        'strategy': 'OpenDownBuy',
                        'pnl_pct': pnl_pct,
                        'pnl_usdt': pnl_usdt,
                        'entry_price': entry_price,
                        'exit_threshold': self.exit_threshold,
                        'open_price_id': position.get('open_price_id', 'unknown'),
                    }
                )

                logger.info(
                    f"✅ POSICIÓN CERRADA: PnL {pnl_pct:.2f}% ({pnl_usdt:+.2f} USDT)"
                )

            logger.info(f"🎯 Total posiciones cerradas: {len(positions_to_close)}")
            logger.info(f"ℹ️  'has_bought_today' sigue en True - No se comprará más hasta mañana")

    async def _notify_pnl(self, current_price: float, current_time: datetime):
        """Notifica PnL actual de todas las posiciones cada minuto."""
        if len(self.open_positions) == 0:
            return

        # Notificar cada 60 segundos
        if (
            self.last_pnl_notification is None
            or (current_time - self.last_pnl_notification).total_seconds() >= 60
        ):
            # Calcular PnL total y promedio
            total_pnl_pct = 0.0
            total_pnl_usdt = 0.0

            for position in self.open_positions:
                entry_price = position['entry_price']
                if entry_price and entry_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    pnl_usdt = self.base_capital * (pnl_pct / 100.0)
                    total_pnl_pct += pnl_pct
                    total_pnl_usdt += pnl_usdt

            avg_pnl_pct = total_pnl_pct / len(self.open_positions) if len(self.open_positions) > 0 else 0.0

            change_from_open_pct = (
                (current_price - self.daily_open_price) / self.daily_open_price
            ) * 100

            logger.info(
                f"📊 PnL Promedio: {avg_pnl_pct:+.2f}% | Total: {total_pnl_usdt:+.2f} USDT | "
                f"Posiciones: {len(self.open_positions)} | "
                f"Desde apertura: {change_from_open_pct:+.2f}% "
                f"(meta salida: {self.exit_threshold}%)"
            )

            self.last_pnl_notification = current_time

    async def _wait_for_confirmation(self, timeout: float = 5.0) -> bool:
        """Espera confirmación de la orden."""
        try:
            confirmation = await asyncio.wait_for(
                self.confirmation_queue.get(), timeout=timeout
            )

            if confirmation and confirmation.get('symbol') == self.symbol:
                if confirmation.get('status') == 'OPEN':
                    logger.info("✅ Confirmación recibida: Orden ABIERTA")
                    return True
                else:
                    logger.warning(
                        f"⚠️ Orden RECHAZADA: {confirmation.get('response')}"
                    )

            return False

        except asyncio.TimeoutError:
            logger.warning("⏱️ Timeout esperando confirmación")
            return False
        except Exception as e:
            logger.error(f"Error esperando confirmación: {e}")
            return False

    async def on_start(self):
        """Hook ejecutado al iniciar la estrategia."""
        # Inicializar precio de apertura diaria
        current_time = datetime.now(timezone.utc)
        current_price = 0.0  # Placeholder, se actualizará en primera vela

        # Cargar precio de apertura desde API
        await self._initialize_daily_open(current_price, current_time)

        logger.info("=" * 60)
        logger.info("ESTRATEGIA OpenDownBuy INICIADA")
        logger.info(f"  Símbolo: {self.symbol}")
        logger.info(f"  Timeframe: {self.timeframe}")
        logger.info(f"  Umbral Entrada: {self.entry_threshold}%")
        logger.info(f"  Umbral Salida: {self.exit_threshold}%")
        logger.info(f"  Capital Base: {self.base_capital} USDT")
        logger.info(f"  Tamaño Posición: {self.position_size_percent}%")
        if self.daily_open_price:
            logger.info(f"  Apertura Diaria: {self.daily_open_price:.2f} USDT")
        logger.info("=" * 60)

