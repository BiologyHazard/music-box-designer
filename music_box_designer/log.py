from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import loguru

if TYPE_CHECKING:
    from loguru import Logger, Record

# default_format: str = '{asctime} [{levelname}] {module} | {message}'
# default_date_format: str = '%Y-%m-%d %H:%M:%S'
# logging.basicConfig(level=logging.DEBUG, format=default_format, datefmt=default_date_format, style='{')

default_format: str = (
    '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> '
    '[<level>{level}</level>] '
    '<cyan><underline>{name}</underline></cyan>:'
    '<cyan>{function}</cyan>:<cyan>{line}</cyan> | '
    '<level><normal>{message}</normal></level>'
)


def default_filter(record: Record) -> bool:
    levelno: int = logger.level(log_level).no if isinstance(log_level, str) else log_level
    return record['level'].no >= levelno


logger: Logger = loguru.logger


logger.remove()
logger_id: int = logger.add(
    sys.stderr,
    level=0,
    format=default_format,
    filter=default_filter,
)

log_level: str | int = 'INFO'


def set_level(level: str | int) -> None:
    global log_level
    log_level = level
