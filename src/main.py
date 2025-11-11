import asyncio
from config.settings import settings
from persistence.db_connection import db
from persistence.test_db import run_all_db_tests
from persistence.test_repos import run_repository_tests
from strategies import BBANDS_RSI_MeanReversionStrategy
from strategies.btc_rsi import BTC_RSI_Strategy
from strategies.OpenDownBuyStrategy import BTC_Daily_Open_Strategy
from engine.trade_engine import TradeEngine
from persistence.repositories.bot_config_repository import BotConfigRepository
from persistence.repositories.bot_run_repository import BotRunRepository

settings = settings

# 🔧 CONFIGURACIÓN FLEXIBLE DE ESTRATEGIAS
STRATEGY_CONFIGS = {
    "bbands_rsi": {
        "class": BBANDS_RSI_MeanReversionStrategy,
        "name": "BBANDS RSI Mean Reversion",
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"],
        "params": {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_buy_threshold": 40.0,
            "rsi_sell_threshold": 60.0,
            "sma_period": 50,
            "vol_sma_period": 20,
            "enforce_volume_filter": True,
            "max_holding_hours": 48,
            "timeframe": "1m"
        }
    },
    "btc_rsi": {
        "class": BTC_RSI_Strategy,
        "name": "BTC RSI Strategy",
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"],
        "params": {
            "rsi_period": 14,
            "overbought": 70,
            "oversold": 30
        }
    },
    "btc_daily": {
        "class": BTC_Daily_Open_Strategy,
        "name": "BTC Daily Open Strategy",
        "symbols": ["BTCUSDT"],  # Solo BTC para esta estrategia
        "params": {
            "entry_threshold": -1.0,
            "exit_threshold": 2.0,
            "position_size_percent": 100.0,
            "base_capital": 10.0,
            "symbol": "BTCUSDT"
        }
    }
}


def print_strategy_options():
    """Muestra las estrategias disponibles"""
    print("\n🎯 ESTRATEGIAS DISPONIBLES:")
    for key, config in STRATEGY_CONFIGS.items():
        print(f"   🔹 {key}: {config['name']}")
        print(f"      Símbolos: {config['symbols']}")
        print(f"      Parámetros: {config['params']}")
        print()


async def main():
    # Asegurar tablas
    db.create_tables()

    # Crear sesión y asegurar BotConfig -  Persistir en BD
    session = db.get_session()
    bot_repo = BotConfigRepository(session)
    bot = bot_repo.create_if_not_exists(name="Bot", exchange="BINANCE", mode="REAL")

    # Iniciar un BotRun
    run_repo = BotRunRepository(session)
    run = run_repo.start(bot_id=bot.id, mode=bot.mode, env="dev", run_id=None)

    # Se crea la cola de señales
    signal_queue = asyncio.Queue()

    print("Iniciando prueba de conexión a la base de datos...")
    print(f"Modo de operación: {settings.MODE}")
    print(f"URL de REST: {settings.REST_URL}")
    print(f"URL de WebSocket: {settings.WS_URL}")
    print(f"URL de la Base de Datos: {settings.DATABASE_URL}")

    run_all_db_tests()
    run_repository_tests()
    print("✅ Todas las pruebas completadas.")
    print("-------------------------------------------------")

    # SELECCIÓN DE ESTRATEGIA
    print_strategy_options()

    # Estrategia por defecto - Pruebas
    selected_strategy = "btc_daily"

    # Para selección manual por consola
    # selected_strategy = input("Ingresa el nombre de la estrategia a usar: ").strip().lower()

    if selected_strategy not in STRATEGY_CONFIGS:
        available_strategies = ", ".join(STRATEGY_CONFIGS.keys())
        print(f"Estrategia '{selected_strategy}' no encontrada.")
        print(f"Estrategias disponibles: {available_strategies}")
        # Usar estrategia por defecto
        selected_strategy = "btc_daily"
        print(f"Usando estrategia por defecto: {selected_strategy}")

    config = STRATEGY_CONFIGS[selected_strategy]

    print(f"\nINICIANDO ESTRATEGIA: {config['name']}")
    print(f"Símbolos: {config['symbols']}")
    print(f"    Parámetros: {config['params']}")
    print("-------------------------------------------------")

    # Cola opcional para confirmaciones entre TradeEngine -> Estrategia
    confirmation_queue = asyncio.Queue()

    # Crear instancia de la estrategia (pasando confirmation_queue)
    strategy = config["class"](
        signal_queue=signal_queue,
        bot_id=bot.id,
        run_db_id=run.id,
        confirmation_queue=confirmation_queue,
        **config["params"]
    )

    # Crear TradeEngine con la queue de confirmaciones
    trade_engine = TradeEngine(signal_queue=signal_queue, bot_id=bot.id, run_db_id=run.id, confirmation_queue=confirmation_queue)

    try:
        await asyncio.gather(
            strategy.start(symbols=config["symbols"]),
            trade_engine.start()
        )
    except KeyboardInterrupt:
        print("\nDeteniendo bot...")
    except Exception as e:
        print(f"Error crítico: {e}")
    finally:
        # Cerrar el BotRun al finalizar
        run_repo.end(run_db_id=run.id, status="stopped")
        session.close()
        print("Bot detenido correctamente.")


if __name__ == "__main__":
    asyncio.run(main())