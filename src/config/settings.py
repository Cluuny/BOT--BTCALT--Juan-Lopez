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
    load_dotenv()


class Settings:
    # Configuración Binance
    MODE: str = os.getenv("MODE", "TESTNET").upper()
    API_KEY: str = os.getenv("API_KEY")
    API_SECRET: str = os.getenv("API_SECRET")
    WS_URL: str = "wss://stream.binance.com:9443/ws"

    # NOTA: No validar aquí para permitir import en entornos de test/offline.
    # Validación se realiza al instanciar el cliente REST.

    if MODE == "TESTNET":
        REST_URL = "https://testnet.binance.vision/api"
    else:
        REST_URL = "https://api.binance.com"

    # Configuración Base de Datos
    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "trading_bot")
    DB_USER = os.getenv("DB_USER", "trading_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "trading_pass")

    print(DB_PASSWORD)

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def validate_api_keys(self) -> None:
        """
        Validar que API_KEY / API_SECRET estén presentes.
        Llamar desde el cliente REST antes de instanciar la librería externa.
        """
        if not self.API_KEY or not self.API_SECRET:
            raise ValueError("⚠️ API_KEY y API_SECRET deben estar definidas en el .env o variables de entorno")


settings = Settings()
