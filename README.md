# 🤖 Bot de Trading Automatizado - Framework Completo

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-EnhancedBaseStrategy-green.svg)]()
[![Exchange](https://img.shields.io/badge/Exchange-Binance-yellow.svg)](https://www.binance.com/)

Sistema completo de trading automatizado con framework modular para crear estrategias de forma simple y eficiente.

---

## 🎯 ¿Qué es este proyecto?

Un **framework completo de trading** que te permite:

✅ **Crear estrategias** en minutos (no horas)  
✅ **Hacer backtesting** con datos históricos  
✅ **Ejecutar en vivo** con gestión automática de posiciones  
✅ **Gestionar riesgo** con parámetros configurables  
✅ **Visualizar resultados** con métricas detalladas  

---

## 🚀 Quick Start

### 1️⃣ Instalación

```bash
# Clonar repositorio
git clone <tu-repo>
cd Bot

# Crear entorno virtual
python -m venv .binance-bot-venv

# Activar entorno (Windows)
.binance-bot-venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2️⃣ Configuración

Crea un archivo `.env` con tus credenciales:

```env
# Binance API
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET_KEY=tu_secret_key

# Modo (paper/live)
MODE=paper

# URLs
REST_URL=https://testnet.binance.vision
WS_URL=wss://testnet.binance.vision

# Base de datos
DATABASE_URL=sqlite:///bot.db
```

### 3️⃣ Ejecutar

```bash
python src/main.py
```

---

## 📚 Documentación

### 📖 Guías Disponibles:

1. **[FRAMEWORK_GUIDE.md](FRAMEWORK_GUIDE.md)** - Guía completa del framework
   - Arquitectura del sistema
   - Cómo crear estrategias
   - Componentes del framework
   - Ejemplos completos

2. **[Tutorial_Backtesting.ipynb](backtest/Tutorial_Backtesting.ipynb)** - Tutorial de backtesting
   - Paso a paso para hacer backtesting
   - Cálculo de indicadores
   - Análisis de resultados
   - Optimización de parámetros

---

## 🎨 Crear Tu Primera Estrategia

### Ejemplo: Estrategia RSI Simple

```python
from strategies.core.enhanced_base_strategy import EnhancedBaseStrategy

class MiEstrategiaRSI(EnhancedBaseStrategy):
    """Compra cuando RSI < 30, vende cuando RSI > 70"""
    
    def __init__(self, *args, rsi_period=14, oversold=30, overbought=70, **kwargs):
        super().__init__(*args, **kwargs)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
    
    def setup_indicators(self):
        """Define los indicadores a usar"""
        self.indicators.add_rsi(period=self.rsi_period)
    
    async def check_conditions(self, symbol, candle, indicators):
        """Tu lógica de trading"""
        rsi = indicators.get('RSI')
        price = candle['close']
        
        # Señal de compra
        if rsi < self.oversold:
            await self.emit_buy(symbol, price, f"RSI={rsi:.2f} sobrevendido")
        
        # Señal de venta
        elif rsi > self.overbought:
            await self.emit_sell(symbol, price, f"RSI={rsi:.2f} sobrecomprado")
```

---

## 🔥 Resolución del Error AttributeError

### ✅ **SOLUCIONADO**

**Error anterior:**
```python
AttributeError: type object 'EnhancedBaseStrategy' has no attribute 'RiskParameters'
```

**Solución implementada:**
1. Creada la dataclass `RiskParameters` en `enhanced_base_strategy.py`
2. Asignada como atributo de clase: `EnhancedBaseStrategy.RiskParameters = RiskParameters`
3. Exportada desde `strategies.core.__init__.py`
4. Actualizado `position_manager.py` para importar correctamente

**Verificación:**
```bash
python test_imports.py
# ✅ Todos los imports funcionan correctamente!
```

---

## 📊 Estrategias Incluidas

1. **BBANDS_RSI_MeanReversion** - Reversión a la media con BB y RSI
2. **BTC_RSI_Strategy** - Estrategia simple basada en RSI
3. **OpenDownBuyStrategy** - Compra cuando el precio baja en apertura
4. **DownALTBuyer** - Compra ALTs cuando BTC baja
5. **SimpleMeanReversionStrategy** - Reversión a la media con BB

---

## ⚠️ Disclaimer

Este software es **solo para fines educativos**. Trading de criptomonedas conlleva riesgos significativos. Usa bajo tu propio riesgo.

---

## 🎉 ¡Comienza Ahora!

```bash
# 1. Instalar
pip install -r requirements.txt

# 2. Configurar tu .env

# 3. Ejecutar
python src/main.py
```

**Lee la [Guía Completa del Framework](FRAMEWORK_GUIDE.md) para más detalles.**

**¡Happy Trading! 🚀📈**

