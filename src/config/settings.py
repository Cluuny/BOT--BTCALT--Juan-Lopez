import os
from dotenv import load_dotenv
from pathlib import Path


def _find_dotenv(start_path: Path, name: str = ".env") -> Path | None:
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
    load_dotenv()


class Settings:
    # Configuración Binance - CORREGIDO
    MODE: str = os.getenv("MODE", "REAL").upper()
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    WS_URL: str = "wss://stream.binance.com:9443/ws"

    if MODE == "TESTNET":
        REST_URL = "https://testnet.binance.vision/api"
    else:
        REST_URL = "https://api.binance.com"

    # Configuración Base de Datos - CORREGIDO
    DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "trading_bot")
    DB_USER = os.getenv("POSTGRES_USER", "trading_user")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "trading_pass")

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def validate_api_keys(self) -> None:
        """Validar que las credenciales de Binance estén presentes"""
        if not self.BINANCE_API_KEY or not self.BINANCE_API_SECRET:
            raise ValueError("⚠️ BINANCE_API_KEY y BINANCE_API_SECRET deben estar definidas")


settings = Settings()