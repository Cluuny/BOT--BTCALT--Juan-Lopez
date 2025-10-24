import os
from dotenv import load_dotenv
from pathlib import Path


def _find_dotenv(start_path: Path, name: str = ".env") -> Path | None:
    # Busca .env ascendiendo desde la ubicación del archivo hasta la raíz del disco
    p = start_path.resolve()
    for candidate in [p] + list(p.parents):
        env_file = candidate / name
        if env_file.exists():
            return env_file
    return None


_env_path = _find_dotenv(Path(__file__))
if _env_path:
    load_dotenv(_env_path)
else:
    # Fallback: intenta cargar .env desde cwd (comportamiento por defecto)
    load_dotenv()


class Settings:
    # Configuración Binance
    MODE: str = os.getenv("MODE", "TESTNET").upper()
    API_KEY: str = os.getenv("API_KEY")
    API_SECRET: str = os.getenv("API_SECRET")

    if not API_KEY or not API_SECRET:
        raise ValueError("⚠️ API_KEY y API_SECRET deben estar en el .env")

    # Endpoints según el modo
    if MODE == "TESTNET":
        REST_URL = "https://testnet.binance.vision/api"
        WS_URL = "wss://testnet.binance.vision/ws"
    else:
        REST_URL = "https://api.binance.com"
        WS_URL = "wss://stream.binance.com:9443/ws"

    # Configuración Base de Datos
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "trading_bot")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
