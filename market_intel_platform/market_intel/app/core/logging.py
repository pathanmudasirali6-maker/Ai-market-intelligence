import sys
from loguru import logger
from app.core.config import settings


def setup_logging():
    """Configure structured logging with loguru."""
    logger.remove()  # Remove default handler

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # File handler - rotates daily, keeps 7 days
    logger.add(
        "logs/market_intel_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="DEBUG",
        rotation="00:00",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe async logging
    )

    # Error-only file
    logger.add(
        "logs/errors_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        enqueue=True,
    )

    logger.info(f"Logging initialized | app={settings.APP_NAME} | debug={settings.DEBUG}")
    return logger
