# Minimal harness para pruebas de backtest usadas en tests/test_backtest_flow.py
import csv
from pathlib import Path
from typing import List, Dict, Any


def load_csv(path: str, max_rows: int = None) -> List[Dict[str, Any]]:
    rows = []
    with open(path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            # convertir campos numéricos si es posible
            for k, v in r.items():
                try:
                    if v is None or v == '':
                        continue
                    r[k] = float(v)
                except Exception:
                    pass
            rows.append(r)
    return rows


class SimpleBacktest:
    """Implementación simplificada y determinística para tests.
    - run_rsi_mean_reversion: genera un trade ficticio si hay datos
    - save_outputs: escribe archivos trades, summary y report
    """

    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
        self.trades = []
        self.summary = {}

    def run_rsi_mean_reversion(self):
        # Si hay datos, crear un trade ficticio de ejemplo
        if not self.data:
            self.trades = []
            self.summary = {"pnl": 0.0, "total_trades": 0, "sharpe": 0.0, "max_drawdown_pct": 0.0}
            return

        # trade de ejemplo: compra en primer precio, venta en último
        first = self.data[0]
        last = self.data[-1]
        # intentar extraer un precio de columnas comunes
        price_keys = ["close", "Close", "price", "Price", "c"]
        def get_price(d):
            for k in price_keys:
                if k in d:
                    return float(d[k])
            # fallback: primera numeric value
            for v in d.values():
                if isinstance(v, (int, float)):
                    return float(v)
            return 0.0

        entry_price = get_price(first)
        exit_price = get_price(last)
        qty = 1.0
        pnl = (exit_price - entry_price) * qty

        self.trades = [
            {"entry_price": entry_price, "exit_price": exit_price, "qty": qty, "pnl": pnl}
        ]

        self.summary = {
            "pnl": pnl,
            "total_trades": 1,
            "sharpe": 0.0,
            "max_drawdown_pct": 0.0,
        }

    def save_outputs(self, out_dir: Path) -> Dict[str, str]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        trades_csv = out_dir / 'trades.csv'
        summary_csv = out_dir / 'summary.csv'
        report_html = out_dir / 'report.html'

        # escribir trades
        with open(trades_csv, 'w', newline='') as f:
            if self.trades:
                keys = list(self.trades[0].keys())
            else:
                keys = ['entry_price', 'exit_price', 'qty', 'pnl']
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for t in self.trades:
                writer.writerow(t)

        # escribir summary (una fila)
        with open(summary_csv, 'w', newline='') as f:
            keys = ['pnl', 'total_trades', 'sharpe', 'max_drawdown_pct']
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            row = {k: self.summary.get(k, 0) for k in keys}
            writer.writerow(row)

        # report html simple
        with open(report_html, 'w', encoding='utf-8') as f:
            f.write(f"<html><body><h1>Backtest report</h1><pre>{self.summary}</pre></body></html>")

        return {"trades_csv": str(trades_csv), "summary_csv": str(summary_csv), "report_html": str(report_html)}

