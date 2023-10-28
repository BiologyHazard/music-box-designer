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
    "<level><normal>{message}</normal></level>"
    # "<level>{message}</level>"
)

logger.remove()
logger_id: int = logger.add(
    sys.stderr,
    level="DEBUG",
    format=default_format,
)


def set_level(level: str | int) -> int:
    global logger_id
    logger.remove(logger_id)
    logger_id = logger.add(
        sys.stderr,
        level=level,
        format=default_format,
    )
    return logger_id
