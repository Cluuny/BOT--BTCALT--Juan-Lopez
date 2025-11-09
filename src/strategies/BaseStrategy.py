from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    @abstractmethod
    def _request_for_init(self, symbols: list[str]):
        pass

    @abstractmethod
    async def _handle_update(self, last_candles: dict):
        pass

    @abstractmethod
    async def start(self, symbols: list[str]):
        pass

    class RiskParameters:
        def __init__(
            self,
            # --- Exposicion por operacion ---
            position_size=-1,  # Porcentaje del capital a arriesgar por operación
            max_risk_per_trade=-1,  # Riesgo máximo por operación (en % del equity)
            leverage=-1,  # Apalancamiento usado
            stop_loss_pct=-1,  # Stop Loss relativo (%)
            take_profit_pct=-1,  # Take Profit relativo (%)
            risk_reward_ratio=-1,  # Relación riesgo/beneficio mínima
            # --- Exposicion total (cartera) ---
            max_open_positions=-1,  # Número máximo de posiciones simultáneas
            max_sector_exposure=-1,  # % máximo del capital en un mismo sector
            max_symbol_exposure=-1,  # % máximo del capital en un mismo activo
            # --- Riesgo de capital (drawdown y limites globales) ---
            max_drawdown=-1,  # Drawdown máximo permitido (%)
            max_daily_loss=-1,  # Pérdida máxima diaria permitida (%)
            max_weekly_loss=-1,  # Pérdida máxima semanal permitida (%)
            max_total_loss=-1,  # Pérdida total acumulada máxima (%)
            # --- Gestion de posicion ---
            trailing_stop_pct=-1,  # Stop dinámico (%), -1 si no aplica
            cooldown_period=-1,  # Tiempo mínimo (en minutos) entre trades
            allow_pyramiding=False,  # Permitir añadir a una posición existente
            max_additions=-1,  # Nº máximo de adiciones si pyramiding=True
            partial_take_profit_levels=-1,  # Lista o número de niveles de TP parcial
            # --- Gestion temporal ---
            max_holding_time=-1,  # Tiempo máximo de mantener posición (minutos)
            session_start=-1,  # Hora de inicio de operativa (HHMM o timestamp)
            session_end=-1,  # Hora de fin de operativa
            cooldown_after_loss=-1,  # Minutos de pausa tras una pérdida
            # --- Validacion de señal / condiciones externas ---
            news_filter_enabled=False,  # Filtrar por noticias
            volatility_threshold=-1,  # Volatilidad mínima o máxima tolerada (por ATR, etc.)
            correlation_limit=-1,  # Correlación máxima permitida con otra posición
        ):
            # Asignaciones
            self.position_size = position_size
            self.max_risk_per_trade = max_risk_per_trade
            self.leverage = leverage
            self.stop_loss_pct = stop_loss_pct
            self.take_profit_pct = take_profit_pct
            self.risk_reward_ratio = risk_reward_ratio

            self.max_open_positions = max_open_positions
            self.max_sector_exposure = max_sector_exposure
            self.max_symbol_exposure = max_symbol_exposure

            self.max_drawdown = max_drawdown
            self.max_daily_loss = max_daily_loss
            self.max_weekly_loss = max_weekly_loss
            self.max_total_loss = max_total_loss

            self.trailing_stop_pct = trailing_stop_pct
            self.cooldown_period = cooldown_period
            self.allow_pyramiding = allow_pyramiding
            self.max_additions = max_additions
            self.partial_take_profit_levels = partial_take_profit_levels

            self.max_holding_time = max_holding_time
            self.session_start = session_start
            self.session_end = session_end
            self.cooldown_after_loss = cooldown_after_loss

            self.news_filter_enabled = news_filter_enabled
            self.volatility_threshold = volatility_threshold
            self.correlation_limit = correlation_limit

        def __str__(self):
            # Filtra atributos con valores distintos de -1 o True
            atributos = {
                k: v
                for k, v in vars(self).items()
                if v != -1 and not (isinstance(v, bool) and v is False)
            }

            if not atributos:
                return "RiskParameters: todos los valores están por defecto (-1 o False)"

            # Crea una cadena formateada tipo "nombre=valor"
            contenido = ', '.join(f"{k}={v}" for k, v in atributos.items())
            return f"RiskParameters({contenido})"
