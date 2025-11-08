from utils.logger import Logger
import pandas as pd
import pandas_ta as ta
import asyncio
import traceback
from datetime import datetime, timedelta

from strategies.BaseStrategy import BaseStrategy

from data.ws_BSM_provider import RealTimeDataCollector
from data.rest_data_provider import BinanceRESTClient
from persistence.db_connection import db
from persistence.repositories.signal_repository import SignalRepository

from contracts.signal_contract import RSISignalContract, ValidatedSignal

logger = Logger.get_logger(__name__)


class BBANDS_RSI_MeanReversionStrategy(BaseStrategy):
    """
    Estrategia de reversión a la media usando:
    - Bollinger Bands (20, 2)
    - RSI(14)
    - SMA(50) como filtro de tendencia
    - Filtro de Volumen: SMA volumen(20)

    Entradas BUY cuando:
      close <= BB inferior
      RSI <= 40
      close > SMA50
      (opcional) volume > SMA20(volume)
    """

    def __init__(
            self,
            signal_queue: asyncio.Queue,
            bot_id: int,
            run_db_id: int | None = None,
            bb_period: int = 20,
            bb_std: float = 2.0,
            rsi_period: int = 14,
            rsi_buy_threshold: float = 40.0,
            rsi_sell_threshold: float = 60.0,
            sma_period: int = 50,
            vol_sma_period: int = 20,
            enforce_volume_filter: bool = True,
            max_holding_hours: int = 48,
            timeframe: str = "1m",
    ):
        self.signal_queue = signal_queue
        self.bot_id = bot_id
        self.run_db_id = run_db_id

        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.sma_period = sma_period
        self.vol_sma_period = vol_sma_period
        self.enforce_volume_filter = enforce_volume_filter
        self.max_holding_delta = timedelta(hours=max_holding_hours)
        self.timeframe = timeframe

        self.candles: dict[str, pd.DataFrame] = {}
        self.rest_client = BinanceRESTClient(testnet=True)

        # Para controlar tiempo máximo en posición (simple: último BUY emitido por símbolo)
        self.last_buy_time: dict[str, datetime] = {}

    # =====================================================
    # 🔹 CARGA INICIAL
    # =====================================================
    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos con manejo de DataFrames pequeños."""
        if len(df) < 5:
            return df

        try:
            result_df = df.copy()

            # Bollinger Bands - solo si hay suficientes datos
            if len(result_df) >= self.bb_period:
                bb = ta.bbands(result_df["close"], length=self.bb_period, std=self.bb_std)
                if bb is not None:
                    # Formato específico de pandas_ta: BBL_20_2.0_2.0
                    suffix = f"{self.bb_period}_{self.bb_std}_{self.bb_std}"
                    bbl_col = f"BBL_{suffix}"
                    bbm_col = f"BBM_{suffix}"
                    bbu_col = f"BBU_{suffix}"

                    # Asignar directamente las columnas
                    result_df['BBL'] = bb[bbl_col]
                    result_df['BBM'] = bb[bbm_col]
                    result_df['BBU'] = bb[bbu_col]
                else:
                    logger.warning("Bollinger Bands calculation returned None")

            # RSI
            if len(result_df) >= self.rsi_period:
                result_df["RSI"] = ta.rsi(result_df["close"], length=self.rsi_period)
            else:
                result_df["RSI"] = None

            # SMA50 tendencia
            if len(result_df) >= self.sma_period:
                result_df["SMA50"] = ta.sma(result_df["close"], length=self.sma_period)
            else:
                result_df["SMA50"] = None

            # Volumen SMA20
            if len(result_df) >= self.vol_sma_period:
                result_df["VOL_SMA20"] = ta.sma(result_df["volume"], length=self.vol_sma_period)
            else:
                result_df["VOL_SMA20"] = None

            return result_df.reset_index(drop=True)

        except Exception as e:
            logger.error(f"Error calculando indicadores: {e}")
            return df

    def _request_for_init(self, symbols: list[str]):
        """Solicita datos históricos iniciales para los símbolos."""
        # Necesitamos al menos 50 velas para SMA50 y 20 para BB/volumen
        limit = max(self.sma_period, self.bb_period, self.vol_sma_period) + 5
        response = self.rest_client.get_all_klines(
            list_symbols=symbols, interval=self._interval_to_binance(self.timeframe), limit=limit
        )

        for symbol, data in response.items():
            df = pd.DataFrame(data)
            df = self._compute_indicators(df)
            self.candles[symbol] = df

        logger.info(
            f"✅ Datos históricos iniciales cargados para estrategia BBANDS_RSI_MR ({len(symbols)} símbolos)."
        )

    # =====================================================
    # 🔹 ACTUALIZACIÓN EN TIEMPO REAL
    # =====================================================
    async def _handle_update(self, last_candles: dict):
        """
        Actualiza los DataFrames con nuevas velas cerradas recibidas del WebSocket.
        VERSIÓN CORREGIDA - Solo emite señales válidas
        """
        for symbol, kline in last_candles.items():
            try:
                open_time = int(kline[1])
                close_time = int(kline[2])
                open_p = float(kline[3])
                close_p = float(kline[4])
                high_p = float(kline[5])
                low_p = float(kline[6])
                volume = float(kline[7])

                # Crear nueva fila como diccionario
                new_row = {
                    "open_time": open_time,
                    "close_time": close_time,
                    "open": open_p,
                    "close": close_p,
                    "high": high_p,
                    "low": low_p,
                    "volume": volume,
                }

                if symbol not in self.candles:
                    logger.warning(f"⚠️ No existe DataFrame para {symbol}, se crea uno nuevo.")
                    # Crear DataFrame inicial con la nueva vela
                    df = pd.DataFrame([new_row])
                else:
                    df = self.candles[symbol].copy()

                    # Buscar si ya existe una vela con este close_time
                    mask = df["close_time"] == close_time
                    if mask.any():
                        # Actualizar vela existente
                        idx = mask.idxmax()
                        for col, value in new_row.items():
                            df.at[idx, col] = value
                    else:
                        # AGREGAR NUEVA VELA SIN USAR CONCAT - método más seguro
                        # Crear nueva fila como Series
                        new_series = pd.Series(new_row, name=len(df))

                        # Usar loc para agregar la nueva fila
                        df = df.reset_index(drop=True)
                        df.loc[len(df)] = new_series

                        # Mantener tamaño limitado del DataFrame
                        max_candles = max(self.sma_period, self.bb_period, self.vol_sma_period) + 100
                        if len(df) > max_candles:
                            df = df.iloc[-max_candles:].copy()

                    # Resetear índice para garantizar unicidad
                    df = df.reset_index(drop=True)

                # Calcular indicadores
                df = self._compute_indicators(df)
                self.candles[symbol] = df

                # Extraer últimos valores con manejo seguro de NaN/None
                if len(df) == 0:
                    logger.warning(f"DataFrame vacío para {symbol}, saltando...")
                    continue

                last_row = df.iloc[-1]

                rsi_value = float(last_row["RSI"]) if pd.notna(last_row.get("RSI")) else None
                sma50 = float(last_row["SMA50"]) if pd.notna(last_row.get("SMA50")) else None

                # USAR NOMBRES SIMPLIFICADOS PARA BOLLINGER BANDS
                bbl_col = 'BBL'
                bbm_col = 'BBM'
                bbu_col = 'BBU'

                bbl = float(last_row[bbl_col]) if bbl_col in df.columns and pd.notna(last_row.get(bbl_col)) else None
                bbm = float(last_row[bbm_col]) if bbm_col in df.columns and pd.notna(last_row.get(bbm_col)) else None
                bbu = float(last_row[bbu_col]) if bbu_col in df.columns and pd.notna(last_row.get(bbu_col)) else None

                vol_sma = float(last_row["VOL_SMA20"]) if "VOL_SMA20" in df.columns and pd.notna(
                    last_row.get("VOL_SMA20")) else None

                # Logging seguro que maneja valores None
                bbl_str = f"{bbl:.4f}" if bbl is not None else "NA"
                sma50_str = f"{sma50:.4f}" if sma50 is not None else "NA"
                rsi_str = f"{rsi_value:.2f}" if rsi_value is not None else "NA"

                logger.info(
                    f"✅ {symbol} actualizado — Cierre: {close_p:.4f} | RSI: {rsi_str} | "
                    f"BB Lower: {bbl_str} | SMA50: {sma50_str}"
                )

                indicator_snapshot = {
                    "RSI": rsi_value,
                    "close": close_p,
                    "BB_lower": bbl,
                    "BB_middle": bbm,
                    "BB_upper": bbu,
                    "SMA50": sma50,
                    "volume": volume,
                    "VOL_SMA20": vol_sma,
                }

                # --------- Condición de ENTRADA (BUY) ---------
                buy_conditions = [
                    (bbl is not None and close_p <= bbl),
                    (rsi_value is not None and rsi_value <= self.rsi_buy_threshold),
                    (sma50 is not None and close_p > sma50),
                ]

                if self.enforce_volume_filter:
                    buy_conditions.append(vol_sma is not None and volume > vol_sma)

                if all(buy_conditions):
                    reason = "close<=BB_lower & RSI<=40 & close>SMA50" + (
                        " & vol>vol_sma" if self.enforce_volume_filter else "")

                    # ✅ Solo emitir si RSI es válido
                    if rsi_value is not None:
                        await self._emit_signal(
                            symbol=symbol,
                            signal_type="BUY",
                            price=close_p,
                            rsi=rsi_value,  # ✅ Sin "or 0.0"
                            reason=reason,
                            indicator_snapshot=indicator_snapshot,
                        )
                        self.last_buy_time[symbol] = datetime.utcnow()
                        await asyncio.sleep(0.1)
                    else:
                        logger.warning(f"⚠️ RSI no disponible para {symbol}, señal omitida")
                        continue

                logger.debug("SELL deshabilitado para %s: solo se generan señales BUY", symbol)

            except Exception as e:
                logger.error(f"⚠️ Error procesando actualización de {symbol}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")

    async def _emit_signal(self, symbol: str, signal_type: str, price: float, rsi: float, reason: str,
                           indicator_snapshot: dict):
        """Construye señal validada según contrato RSI - VERSIÓN CORREGIDA"""

        # 🔥 VALIDACIÓN ROBUSTA: No emitir señal si RSI no es válido
        if rsi is None:
            logger.error(f"❌ No se puede emitir señal: RSI es None para {symbol}")
            return

        if not isinstance(rsi, (int, float)):
            logger.error(f"❌ RSI inválido para {symbol}: {rsi} (tipo: {type(rsi)})")
            return

        signal_data = {
            "symbol": symbol,
            "type": signal_type,
            "price": price,
            "rsi": float(rsi),  # ✅ Conversión segura
            "reason": reason,
            "risk_params": self.RiskParameters(),
            "strategy_name": "BBANDS_RSI_MeanReversion"  # ✅ Nombre correcto
        }

        # 🔥 VALIDAR Y NORMALIZAR LA SEÑAL
        validated_signal = ValidatedSignal.create_safe_signal(signal_data)

        if validated_signal is None:
            logger.error(f"❌ Señal inválida descartada para {symbol}")
            return

        # Persistir la señal
        try:
            session = db.get_session()
            repo = SignalRepository(session)
            repo.create(
                bot_id=self.bot_id,
                strategy_name="BBANDS_RSI_MeanReversion",  # ✅ Nombre consistente
                symbol=symbol,
                direction=signal_type,
                price=price,
                params_snapshot={
                    "bb_period": self.bb_period,
                    "bb_std": self.bb_std,
                    "rsi_period": self.rsi_period,
                    "rsi_buy_threshold": self.rsi_buy_threshold,
                    "rsi_sell_threshold": self.rsi_sell_threshold,
                    "sma_period": self.sma_period,
                    "vol_sma_period": self.vol_sma_period,
                    "enforce_volume_filter": self.enforce_volume_filter,
                    "max_holding_hours": self.max_holding_delta.total_seconds() / 3600,
                    "timeframe": self.timeframe,
                    "risk_params": getattr(validated_signal["risk_params"], "__dict__",
                                           str(validated_signal["risk_params"]))
                },
                run_id=self.run_db_id,
                reason=reason,
                indicator_snapshot=indicator_snapshot,
            )
            session.close()
        except Exception as e:
            logger.error(f"Error persistiendo señal {signal_type}: {e}")
            return  # ✅ No emitir señal si falla la persistencia

        # 🔥 ENVIAR SEÑAL VALIDADA
        await self.signal_queue.put(validated_signal)
        logger.info(f"📨 Señal BBANDS_RSI validada: {signal_type} {symbol} @ {price:.4f} — {reason}")
    class RiskParameters(BaseStrategy.RiskParameters):
        def __init__(self):
            super().__init__(max_drawdown=0.5, position_size=0.01, max_open_positions=5)

    # =====================================================
    # 🔹 INICIO DE LA ESTRATEGIA
    # =====================================================
    async def start(self, symbols: list[str]):
        """Inicia la estrategia con datos históricos y actualizaciones en tiempo real."""
        self._request_for_init(symbols=symbols)

        for symbol, df in self.candles.items():
            logger.info(f"Ultimas 3+ velas de {symbol} (BBANDS_RSI_MR):\n{df.tail(3)}")

        collector = RealTimeDataCollector(
            symbols=symbols,
            on_update=self._handle_update,
            interval=self._interval_to_binance(self.timeframe),
        )

        logger.info("Estrategia BBANDS_RSI_MR iniciada. Esperando nuevas velas...")
        await collector.start()

    @staticmethod
    def _interval_to_binance(tf: str) -> str:
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }
        return mapping.get(tf, "1m")