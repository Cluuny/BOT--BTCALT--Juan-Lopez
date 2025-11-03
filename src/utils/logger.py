import logging
import sys

# Opcional: color para consola
class LogColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"

class Logger:
    _configured = False  # Para evitar configurar el logger más de una vez

    @staticmethod
    def get_logger(name: str = "AppLogger"):
        if not Logger._configured:
            Logger._configure_root_logger()
        return logging.getLogger(name)

    @staticmethod
    def _configure_root_logger():
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Handler para consola (stdout)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Configurar el logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)

        Logger._configured = True

# Colores por nivel (opcional)
def colorize_log(record):
    msg = record.getMessage()
    if record.levelno == logging.INFO:
        msg = f"{LogColors.GREEN}{msg}{LogColors.RESET}"
    elif record.levelno == logging.WARNING:
        msg = f"{LogColors.YELLOW}{msg}{LogColors.RESET}"
    elif record.levelno == logging.ERROR:
        msg = f"{LogColors.RED}{msg}{LogColors.RESET}"
    elif record.levelno == logging.DEBUG:
        msg = f"{LogColors.BLUE}{msg}{LogColors.RESET}"
    record.msg = msg
    return True

# Hook para aplicar colores automáticamente
logging.getLogger().addFilter(colorize_log)
