import asyncio
from config.settings import settings
from persistence.db_connection import db
from persistence.test_db import run_all_db_tests
from persistence.test_repos import run_repository_tests
from strategies.btc_rsi import BTC_RSI_Strategy

settings = settings

if __name__ == "__main__":
    print("🧪 Iniciando prueba de conexión a la base de datos...")
    print(f"⚙️  Modo de operación: {settings.MODE}")
    print(f"🔗 URL de REST: {settings.REST_URL}")
    print(f"🔗 URL de WebSocket: {settings.WS_URL}")
    print(f"🗄️  URL de la Base de Datos: {settings.DATABASE_URL}")
    run_all_db_tests()
    run_repository_tests()
    print("✅ Todas las pruebas completadas.")
    print("Cerrando conexión a la base de datos...")
    db.engine.dispose()
    print("Conexión cerrada.")
    print("-------------------------------------------------")
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    strategy = BTC_RSI_Strategy()
    asyncio.run(strategy.start(symbols=symbols))
    print("✅ Bot finalizado correctamente.")
