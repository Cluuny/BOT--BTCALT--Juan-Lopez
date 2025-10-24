from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import importlib
import pkgutil
from config.settings import settings
from persistence import models


Base = declarative_base()


def load_models(package):
    """Importa dinámicamente todos los módulos dentro del paquete 'models'."""
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module_name}")


class Database:
    def __init__(self):
        # settings es la instancia definida en src.config.settings
        self.engine = create_engine(settings.DATABASE_URL, echo=False)
        self.SessionLocal = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )

    def create_tables(self):
        # Carga todos los modelos antes de crear las tablas
        load_models(models)
        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.SessionLocal()


db = Database()
