# bootstrap.py
"""
Inicialización mínima al importar el paquete `src` durante tests.
Evita side-effects pesados (no instanciar clientes externos).
"""
from .utils.logger import Logger

# Configurar logger raíz de forma segura
Logger.get_logger(__name__)

# Placeholder: no ejecutes operaciones de red o DB aquí
