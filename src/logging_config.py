"""
Logging configuration for Farm Scraper
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from loguru import logger as loguru_logger

from src.config import settings


def setup_logging():
    """Configure application logging"""

    # Remove default loguru handler
    loguru_logger.remove()

    # Console handler
    loguru_logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )

    # File handler - rotating logs
    log_file = settings.log_dir / f"farm_scraper_{datetime.now().strftime('%Y%m%d')}.log"

    loguru_logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        level=settings.log_level,
        rotation="500 MB",
        retention="30 days",
        compression="zip"
    )

    # JSON file handler for structured logs (if enabled)
    if settings.log_format == "json":
        json_log_file = settings.log_dir / f"farm_scraper_{datetime.now().strftime('%Y%m%d')}.json"

        loguru_logger.add(
            json_log_file,
            format="{message}",
            level=settings.log_level,
            serialize=True,
            rotation="500 MB",
            retention="30 days"
        )

    # Intercept standard logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level
            try:
                level = loguru_logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Replace standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set third-party library log levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    loguru_logger.info(f"Logging initialized - Level: {settings.log_level}, Format: {settings.log_format}")

    return loguru_logger


# Initialize logging on import
logger = setup_logging()
