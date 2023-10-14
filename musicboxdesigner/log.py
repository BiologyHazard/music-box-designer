import sys

import loguru

# default_format: str = '{asctime} [{levelname}] {module} | {message}'
# default_date_format: str = '%Y-%m-%d %H:%M:%S'
# logging.basicConfig(level=logging.DEBUG, format=default_format, datefmt=default_date_format, style='{')


logger = loguru.logger

default_format: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "[<level>{level}</level>] "
    "<cyan><underline>{name}</underline></cyan>:"
    "<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

logger.remove()
logger_id = logger.add(
    sys.stderr,
    level="DEBUG",
    format=default_format,
)
