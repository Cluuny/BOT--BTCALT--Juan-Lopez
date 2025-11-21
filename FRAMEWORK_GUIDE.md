# 📚 Guía Completa del Framework de Trading y Backtesting

## 🎯 ¿Qué Problema Resuelve Este Framework?

Este framework simplifica **enormemente** la creación de estrategias de trading, permitiéndote enfocarte en **TU LÓGICA DE TRADING** en lugar de preocuparte por:
- ❌ Conexiones a WebSockets
- ❌ Manejo de datos históricos
- ❌ Cálculo de indicadores técnicos
- ❌ Emisión de señales
- ❌ Gestión de posiciones

---

## 🏗️ Arquitectura del Framework

### **Componentes Principales**

```
┌─────────────────────────────────────────────────────────┐
│           EnhancedBaseStrategy (Tu Estrategia)          │
│  ┌────────────────────────────────────────────────┐    │
│  │  setup_indicators()  → Configura indicadores   │    │
│  │  check_conditions()  → Tu lógica de trading    │    │
│  └────────────────────────────────────────────────┘    │
│                          ↓                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ DataManager  │  │IndicatorCalc │  │SignalEmitter │ │
│  │ (Gestiona    │  │ (Calcula RSI,│  │ (Emite BUY/  │ │
│  │  velas)      │  │  BB, SMA...) │  │  SELL/CLOSE) │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │     TradeEngine         │
            │ (Ejecuta órdenes)       │
            └─────────────────────────┘
                          ↓
            ┌─────────────────────────┐
            │   PositionManager       │
            │ (Gestiona posiciones)   │
            └─────────────────────────┘
```

---

## 🚀 Cómo Crear Tu Primera Estrategia

### **Paso 1: Heredar de EnhancedBaseStrategy**

```python
from strategies.core.enhanced_base_strategy import EnhancedBaseStrategy

class MiEstrategia(EnhancedBaseStrategy):
    pass
```

### **Paso 2: Configurar Indicadores**

En `setup_indicators()` defines QUÉ indicadores necesitas:

```python
def setup_indicators(self):
    # Indicadores disponibles:
    self.indicators.add_rsi(period=14)           # RSI
    self.indicators.add_sma(period=50)           # Media Móvil Simple
    self.indicators.add_ema(period=21)           # Media Móvil Exponencial
    self.indicators.add_bbands(period=20, std=2) # Bandas de Bollinger
    self.indicators.add_macd()                   # MACD
```

### **Paso 3: Implementar Tu Lógica**

En `check_conditions()` defines CUÁNDO comprar/vender:

```python
async def check_conditions(self, symbol: str, candle: pd.Series, indicators: Dict[str, float]):
    # Extraer valores
    rsi = indicators.get('RSI')
    sma50 = indicators.get('SMA50')
    close_price = candle['close']
    
    # Tu lógica de trading
    if rsi < 30 and close_price < sma50:
        await self.emit_buy(
            symbol=symbol,
            price=close_price,
            reason="RSI sobrevendido y precio bajo SMA50"
        )
    
    elif rsi > 70:
        await self.emit_sell(
            symbol=symbol,
            price=close_price,
            reason="RSI sobrecomprado"
        )
```

---

## 📊 Ejemplo Completo: Estrategia RSI Simple

```python
from strategies.core.enhanced_base_strategy import EnhancedBaseStrategy
from typing import Dict
import pandas as pd

class SimpleRSIStrategy(EnhancedBaseStrategy):
    """
    Estrategia simple basada en RSI:
    - COMPRA cuando RSI < 30 (sobrevendido)
    - VENDE cuando RSI > 70 (sobrecomprado)
    """
    
    def __init__(self, *args, rsi_period: int = 14, 
                 oversold: float = 30, overbought: float = 70, **kwargs):
        super().__init__(*args, **kwargs)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.positions = {}  # Tracking de posiciones abiertas
    
    def setup_indicators(self):
        """Configura los indicadores que necesitas"""
        self.indicators.add_rsi(period=self.rsi_period)
    
    async def check_conditions(self, symbol: str, candle: pd.Series, 
                               indicators: Dict[str, float]):
        """Tu lógica de trading"""
        rsi = indicators.get('RSI')
        close_price = candle['close']
        
        # Validar que tenemos datos
        if rsi is None:
            return
        
        # 📈 SEÑAL DE COMPRA: RSI en zona de sobreventa
        if rsi < self.oversold and symbol not in self.positions:
            await self.emit_buy(
                symbol=symbol,
                price=close_price,
                reason=f"RSI={rsi:.2f} < {self.oversold} (sobrevendido)",
                metadata={"rsi": rsi}
            )
            self.positions[symbol] = {
                'entry_price': close_price,
                'entry_rsi': rsi
            }
        
        # 📉 SEÑAL DE VENTA: RSI en zona de sobrecompra
        elif rsi > self.overbought and symbol in self.positions:
            entry = self.positions[symbol]
            profit_pct = ((close_price - entry['entry_price']) / entry['entry_price']) * 100
            
            await self.emit_sell(
                symbol=symbol,
                price=close_price,
                reason=f"RSI={rsi:.2f} > {self.overbought} (sobrecomprado), Profit={profit_pct:.2f}%",
                metadata={"rsi": rsi, "profit_pct": profit_pct}
            )
            del self.positions[symbol]
```

---

## 🎮 Cómo Usar Tu Estrategia

### **En main.py:**

```python
# 1. Agregar a STRATEGY_CONFIGS
STRATEGY_CONFIGS = {
    "mi_rsi": {
        "class": SimpleRSIStrategy,
        "name": "Mi Estrategia RSI",
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "params": {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "timeframe": "1m"
        }
    }
}

# 2. Seleccionar estrategia
selected_strategy = "mi_rsi"
```

---

## 🧪 Backtesting con Jupyter Notebooks

### **¿Qué es Backtesting?**

El backtesting te permite **probar tu estrategia con datos históricos** para ver cómo habría funcionado en el pasado.

### **Estructura del Backtest**

```python
# 1. CARGAR DATOS HISTÓRICOS
import pandas as pd

df = pd.read_csv('backtest/SOLUSDT_1m_7y.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.set_index('timestamp')

# 2. CALCULAR INDICADORES
def add_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

df = add_rsi(df)

# 3. SIMULAR TRADING
positions = []
trades = []
cash = 10000  # Capital inicial
position = None

for i in range(len(df)):
    row = df.iloc[i]
    rsi = row['RSI']
    price = row['close']
    
    # Lógica de compra
    if rsi < 30 and position is None:
        shares = cash / price
        position = {
            'entry_price': price,
            'entry_time': row.name,
            'shares': shares
        }
        cash = 0
        print(f"BUY at {price:.2f}, RSI={rsi:.2f}")
    
    # Lógica de venta
    elif rsi > 70 and position is not None:
        sell_value = position['shares'] * price
        profit = sell_value - (position['shares'] * position['entry_price'])
        profit_pct = (profit / (position['shares'] * position['entry_price'])) * 100
        
        trades.append({
            'entry_time': position['entry_time'],
            'exit_time': row.name,
            'entry_price': position['entry_price'],
            'exit_price': price,
            'shares': position['shares'],
            'profit': profit,
            'profit_pct': profit_pct
        })
        
        cash = sell_value
        position = None
        print(f"SELL at {price:.2f}, RSI={rsi:.2f}, Profit={profit_pct:.2f}%")

# 4. ANALIZAR RESULTADOS
trades_df = pd.DataFrame(trades)
print("\n📊 RESULTADOS DEL BACKTEST:")
print(f"Total trades: {len(trades_df)}")
print(f"Ganancia total: ${trades_df['profit'].sum():.2f}")
print(f"Ganancia promedio por trade: {trades_df['profit_pct'].mean():.2f}%")
print(f"Win rate: {(trades_df['profit'] > 0).sum() / len(trades_df) * 100:.2f}%")

# 5. VISUALIZAR
import matplotlib.pyplot as plt

plt.figure(figsize=(15, 8))

# Gráfico 1: Precio y RSI
plt.subplot(2, 1, 1)
plt.plot(df.index, df['close'], label='Precio')
plt.title('Precio de Cierre')
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(df.index, df['RSI'], label='RSI', color='purple')
plt.axhline(y=70, color='r', linestyle='--', label='Sobrecomprado')
plt.axhline(y=30, color='g', linestyle='--', label='Sobrevendido')
plt.title('RSI')
plt.legend()

plt.tight_layout()
plt.show()

# Gráfico 2: Curva de equity
equity = [10000]  # Capital inicial
for trade in trades:
    equity.append(equity[-1] + trade['profit'])

plt.figure(figsize=(15, 5))
plt.plot(equity)
plt.title('Curva de Equity')
plt.xlabel('Trade #')
plt.ylabel('Capital ($)')
plt.grid(True)
plt.show()
```

---

## 🔧 Componentes del Framework Explicados

### **1. DataManager**
**¿Qué hace?** Gestiona velas históricas y en tiempo real.

```python
# Automático: El framework lo gestiona
candles = self.data_manager.get_candles('BTCUSDT')
last_candle = self.data_manager.get_latest_candle('BTCUSDT')
```

### **2. IndicatorCalculator**
**¿Qué hace?** Calcula indicadores técnicos sobre tus datos.

```python
# Indicadores disponibles:
self.indicators.add_rsi(14)        # RSI
self.indicators.add_sma(50)        # SMA
self.indicators.add_ema(21)        # EMA
self.indicators.add_bbands(20, 2)  # Bollinger Bands
self.indicators.add_macd()         # MACD
```

### **3. SignalEmitter**
**¿Qué hace?** Envía señales al TradeEngine para ejecutar órdenes.

```python
# Uso en tu estrategia:
await self.emit_buy(symbol, price, reason)   # Comprar
await self.emit_sell(symbol, price, reason)  # Vender
await self.emit_close(symbol, price, reason) # Cerrar posición
```

### **4. RiskParameters**
**¿Qué hace?** Define parámetros de riesgo para gestión de posiciones.

```python
from strategies.core import RiskParameters

risk = RiskParameters(
    position_size=0.1,        # 10% del capital por trade
    max_open_positions=5,     # Máximo 5 posiciones simultáneas
    stop_loss_pct=2.0,        # Stop loss del 2%
    take_profit_pct=5.0       # Take profit del 5%
)
```

---

## 📈 Métricas de Backtesting

### **Métricas Esenciales:**

1. **Total Trades**: Número de operaciones realizadas
2. **Win Rate**: % de trades ganadores
3. **Profit Factor**: Ganancias totales / Pérdidas totales
4. **Sharpe Ratio**: Retorno ajustado por riesgo
5. **Max Drawdown**: Pérdida máxima desde un pico
6. **Average Profit**: Ganancia promedio por trade

### **Código para Calcular Métricas:**

```python
def calculate_metrics(trades_df):
    total_trades = len(trades_df)
    winners = trades_df[trades_df['profit'] > 0]
    losers = trades_df[trades_df['profit'] < 0]
    
    win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
    
    total_profit = winners['profit'].sum()
    total_loss = abs(losers['profit'].sum())
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    avg_profit = trades_df['profit'].mean()
    
    # Sharpe Ratio (simplificado)
    returns = trades_df['profit_pct']
    sharpe = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0
    
    # Max Drawdown
    equity_curve = trades_df['profit'].cumsum()
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max * 100
    max_drawdown = drawdown.min()
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_profit': avg_profit,
        'sharpe_ratio': sharpe,
        'max_drawdown_pct': max_drawdown
    }

metrics = calculate_metrics(trades_df)
print("📊 MÉTRICAS DE PERFORMANCE:")
for key, value in metrics.items():
    print(f"  {key}: {value:.2f}")
```

---

## 🎯 Ejercicios Prácticos

### **Ejercicio 1: Estrategia de Bandas de Bollinger**

```python
class BollingerStrategy(EnhancedBaseStrategy):
    def setup_indicators(self):
        self.indicators.add_bbands(period=20, std=2)
    
    async def check_conditions(self, symbol, candle, indicators):
        price = candle['close']
        bb_lower = indicators.get('BBL')
        bb_upper = indicators.get('BBU')
        
        # COMPRA cuando el precio toca la banda inferior
        if price <= bb_lower:
            await self.emit_buy(symbol, price, "Precio en banda inferior")
        
        # VENDE cuando el precio toca la banda superior
        elif price >= bb_upper:
            await self.emit_sell(symbol, price, "Precio en banda superior")
```

### **Ejercicio 2: Estrategia de Cruce de Medias**

```python
class MACrossStrategy(EnhancedBaseStrategy):
    def setup_indicators(self):
        self.indicators.add_sma(period=20)  # Media corta
        self.indicators.add_sma(period=50)  # Media larga
        self.last_signal = None
    
    async def check_conditions(self, symbol, candle, indicators):
        sma20 = indicators.get('SMA20')
        sma50 = indicators.get('SMA50')
        
        # Golden Cross: SMA20 cruza por encima de SMA50
        if sma20 > sma50 and self.last_signal != 'buy':
            await self.emit_buy(symbol, candle['close'], "Golden Cross")
            self.last_signal = 'buy'
        
        # Death Cross: SMA20 cruza por debajo de SMA50
        elif sma20 < sma50 and self.last_signal != 'sell':
            await self.emit_sell(symbol, candle['close'], "Death Cross")
            self.last_signal = 'sell'
```

---

## 🐛 Solución de Problemas Comunes

### **Error: AttributeError: 'EnhancedBaseStrategy' has no attribute 'RiskParameters'**
✅ **SOLUCIONADO**: Ahora `RiskParameters` está correctamente definido como dataclass.

### **Error: No hay datos suficientes para indicadores**
```python
# Solución: Aumentar historical_candles
strategy = MiEstrategia(
    ...,
    historical_candles=200  # Aumentar si usas muchos indicadores
)
```

### **Warning: minNotional**
```python
# El PositionManager ahora valida automáticamente minNotional
# Asegúrate de que position_size_usdt > 10 USDT
```

---

## 📚 Recursos Adicionales

### **Archivos Importantes:**
- `src/strategies/core/enhanced_base_strategy.py` - Clase base
- `src/strategies/examples/simple_mean_reversion.py` - Ejemplo completo
- `backtest/harness.py` - Framework de backtesting
- `src/position/position_manager.py` - Gestión de posiciones

### **Próximos Pasos:**
1. ✅ Crea tu primera estrategia simple
2. ✅ Pruébala en backtesting con datos históricos
3. ✅ Optimiza parámetros
4. ✅ Ejecuta en modo paper trading (testnet)
5. ✅ Cuando estés seguro, pasa a producción

---

## 🎉 ¡Estás Listo!

Ahora tienes todas las herramientas para:
- ✅ Crear estrategias de trading complejas fácilmente
- ✅ Hacer backtesting con datos históricos
- ✅ Entender las métricas de performance
- ✅ Integrar todo el framework en tu codebase

**¡Feliz trading! 🚀📈**

