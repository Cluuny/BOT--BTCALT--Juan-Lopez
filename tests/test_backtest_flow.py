import shutil
from pathlib import Path
from backtest.harness import load_csv, SimpleBacktest


def test_backtest_flow(tmp_path):
    # ejecutar backtest con pocas filas para test rápido
    csv_file = Path('backtest/btcusd_m1_7years.csv')
    assert csv_file.exists(), "CSV de backtest no encontrado"

    data = load_csv(str(csv_file), max_rows=500)
    bt = SimpleBacktest(data)
    bt.run_rsi_mean_reversion()
    out = bt.save_outputs(tmp_path)

    # Verificar archivos generados
    trades = Path(out['trades_csv'])
    summary = Path(out['summary_csv'])
    report = Path(out['report_html'])

    assert trades.exists()
    assert summary.exists()
    assert report.exists()

    # Cargar summary y validar claves
    import csv
    with open(summary, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        row = rows[0]
        # claves obligatorias
        assert 'pnl' in row
        assert 'total_trades' in row
        assert 'sharpe' in row
        assert 'max_drawdown_pct' in row

    # Clean up
    shutil.rmtree(tmp_path)

