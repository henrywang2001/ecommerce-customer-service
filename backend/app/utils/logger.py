"""日志工具"""
import logging
import os
from app.core.config import settings


def setup_logger(name: str) -> logging.Logger:
    """配置并返回 logger 实例"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), "INFO"))

        # 控制台 handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # 文件 handler
        if settings.LOG_DIR:
            os.makedirs(settings.LOG_DIR, exist_ok=True)
            file_handler = logging.FileHandler(
                os.path.join(settings.LOG_DIR, "app.log"),
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

    return logger
