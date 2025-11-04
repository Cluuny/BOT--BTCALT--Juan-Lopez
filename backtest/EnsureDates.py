import yfinance as yf
import pandas as pd
from datetime import datetime

# Verificar disponibilidad histórica de cada cripto
tickers = ['BTC-USD', 'ETH-USD', 'XRP-USD', 'ADA-USD', 'DOT-USD', 'DOGE-USD', 'LTC-USD']

print("🔍 VERIFICANDO DISPONIBILIDAD HISTÓRICA:")
print("=" * 50)

for ticker in tickers:
    try:
        # Obtener datos máximos disponibles
        data = yf.download(ticker, period="max", progress=False)
        if not data.empty:
            years = (data.index.max() - data.index.min()).days / 365.25
            print(f"✅ {ticker}: {len(data):>6} días ~ {years:.1f} años | Desde: {data.index.min().strftime('%Y-%m-%d')}")
        else:
            print(f"❌ {ticker}: Sin datos disponibles")
    except Exception as e:
        print(f"❌ {ticker}: Error - {e}")