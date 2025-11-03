import asyncio
from config.settings import settings
from persistence.db_connection import db
from persistence.test_db import run_all_db_tests
from persistence.test_repos import run_repository_tests
from strategies.btc_rsi import BTC_RSI_Strategy
from engine.trade_engine import TradeEngine
from persistence.repositories.bot_config_repository import BotConfigRepository
from persistence.repositories.bot_run_repository import BotRunRepository


settings = settings


async def main():
    # Asegurar tablas
    db.create_tables()

    # Crear sesión y asegurar BotConfig
    session = db.get_session()
    bot_repo = BotConfigRepository(session)
    bot = bot_repo.create_if_not_exists(name="DefaultBot", exchange="BINANCE", mode="TESTNET")

    # Iniciar un BotRun
    run_repo = BotRunRepository(session)
    run = run_repo.start(bot_id=bot.id, mode=bot.mode, env="dev", run_id=None)

    signal_queue = asyncio.Queue()
    print("🧪 Iniciando prueba de conexión a la base de datos...")
    print(f"⚙️  Modo de operación: {settings.MODE}")
    print(f"🔗 URL de REST: {settings.REST_URL}")
    print(f"🔗 URL de WebSocket: {settings.WS_URL}")
    print(f"🗄️  URL de la Base de Datos: {settings.DATABASE_URL}")
    run_all_db_tests()
    run_repository_tests()
    print("✅ Todas las pruebas completadas.")
    print("-------------------------------------------------")
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    # symbols = ["BTCUSDT"]
    strategy = BTC_RSI_Strategy(signal_queue=signal_queue, bot_id=bot.id, run_db_id=run.id)
    trade_engine = TradeEngine(signal_queue=signal_queue, bot_id=bot.id, run_db_id=run.id)

    try:
        await asyncio.gather(strategy.start(symbols=symbols), trade_engine.start())
    finally:
        # Cerrar el BotRun al finalizar
        run_repo.end(run_db_id=run.id, status="stopped")
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
