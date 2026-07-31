import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.config import settings

def configure_logging():
    logger = logging.getLogger()
    logger.setLevel(settings.log_level)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s', rename_fields={"levelname": "level", "asctime": "timestamp"})
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    # Silence chatty libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
