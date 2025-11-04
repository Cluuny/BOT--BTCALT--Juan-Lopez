import os
import time
from datetime import datetime, timedelta, timezone
import pandas as pd

# Nota: yfinance no permite descargar velas de 1 minuto más allá de ~30 días.
# Para 7 años en m1 usaremos la API pública de Binance (python-binance ya está en requirements).
from binance.client import Client
from binance.exceptions import BinanceAPIException


def descargar_btcusd_m1_7años(salida_csv: str = "btcusd_m1_7years.csv") -> str:
    """
    Descarga velas de 1 minuto de BTC/USDT (proxy de BTCUSD) de los últimos 7 años usando Binance.
    - Guarda CSV con columnas: Date (UTC ISO8601), open, high, low, close, volume
    - Respeta límites de 1000 velas por petición, avanzando con startTime.
    - Puede tardar mucho si realmente se ejecuta completo (millones de velas).

    Retorna la ruta del CSV generado (en la carpeta actual).
    """
    print("🚀 Descargando BTCUSD (BTCUSDT en Binance) — timeframe 1m — últimos 7 años")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7 * 365)

    # Binance usa milisegundos desde epoch UTC
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    client = Client()  # sin API key: endpoint público para klines históricos

    interval = Client.KLINE_INTERVAL_1MINUTE
    limit = 1000  # máximo por llamada

    all_rows = []
    curr = start_ms
    calls = 0

    # Archivo temporal para reanudación simple (opcional)
    tmp_csv = salida_csv + ".part"

    while curr < end_ms:
        try:
            kl = client.get_klines(symbol="BTCUSDT", interval=interval, limit=limit, startTime=curr, endTime=end_ms)
        except BinanceAPIException as e:
            print(f"⚠️ BinanceAPIException: {e.status_code} {e.message}. Reintentando en 2s...")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"⚠️ Error en request: {e}. Reintentando en 2s...")
            time.sleep(2)
            continue

        if not kl:
            # No hay más datos
            break

        # klines: [ open_time, open, high, low, close, volume, close_time, ... ]
        for k in kl:
            open_time_ms = int(k[0])
            close_time_ms = int(k[6])
            open_p = float(k[1])
            high_p = float(k[2])
            low_p = float(k[3])
            close_p = float(k[4])
            vol = float(k[5])

            all_rows.append({
                "Date": datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc).isoformat(),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
            })

            curr = close_time_ms + 1  # avanzar al siguiente ms

        calls += 1
        if calls % 50 == 0:
            # Volcado incremental para no perder progreso
            df_tmp = pd.DataFrame(all_rows)
            df_tmp.to_csv(tmp_csv, index=False)
            first_dt = df_tmp["Date"].iloc[0] if len(df_tmp) else "-"
            last_dt = df_tmp["Date"].iloc[-1] if len(df_tmp) else "-"
            print(f"   ⏳ Progreso: {len(all_rows):,} velas | {first_dt} → {last_dt} | llamadas: {calls}")
            # Pausa suave para no golpear rate limit
            time.sleep(0.2)

        # Pequeña espera entre llamadas
        time.sleep(0.05)

    if not all_rows:
        raise RuntimeError("No se obtuvieron datos de klines.")

    df = pd.DataFrame(all_rows)
    # Asegurar orden cronológico
    df["Date"] = pd.to_datetime(df["Date"])  # parse a datetime para ordenar
    df = df.sort_values("Date").reset_index(drop=True)

    # Guardar CSV final en carpeta backtest si se ejecuta desde raíz del proyecto
    out_path = salida_csv
    # Si este script se ejecuta desde backtest/, mantener relativo
    try:
        # Preferir guardar en la misma carpeta del script
        base_dir = os.path.dirname(__file__)
        out_path = os.path.join(base_dir, salida_csv)
    except Exception:
        pass

    df.to_csv(out_path, index=False)

    # Limpiar archivo parcial si existe
    try:
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)
    except Exception:
        pass

    print(f"✅ Guardado: {out_path}")
    print(f"   Registros: {len(df):,} | Rango: {df['Date'].iloc[0]} → {df['Date'].iloc[-1]}")
    return out_path


if __name__ == "__main__":
    # Ejecutar descarga específica solicitada
    descargar_btcusd_m1_7años()