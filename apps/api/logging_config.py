from __future__ import annotations

import logging
import logging.config
import logging.handlers
from pathlib import Path
from typing import Any


class TimeOrSizeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(
        self,
        filename: str,
        when: str = "D",
        interval: int = 2,
        backupCount: int = 30,
        encoding: str | None = "utf-8",
        delay: bool = False,
        utc: bool = False,
        atTime: Any | None = None,
        maxBytes: int = 10 * 1024 * 1024,
    ) -> None:
        super().__init__(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            utc=utc,
            atTime=atTime,
        )
        self.maxBytes = maxBytes

    def shouldRollover(self, record: logging.LogRecord) -> int:
        if super().shouldRollover(record):
            return 1
        if self.maxBytes <= 0:
            return 0
        if self.stream is None:
            self.stream = self._open()
        message = f"{self.format(record)}\n"
        self.stream.seek(0, 2)
        if self.stream.tell() + len(message.encode(self.encoding or "utf-8")) >= self.maxBytes:
            return 1
        return 0


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    app_log = str(log_dir / "app.log")
    access_log = str(log_dir / "access.log")

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
            "access": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(client_addr)s - \"%(request_line)s\" %(status_code)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "app_file": {
                "()": "apps.api.logging_config.TimeOrSizeRotatingFileHandler",
                "filename": app_log,
                "when": "D",
                "interval": 2,
                "backupCount": 30,
                "maxBytes": 10485760,
                "formatter": "default",
                "encoding": "utf-8",
            },
            "access_file": {
                "()": "apps.api.logging_config.TimeOrSizeRotatingFileHandler",
                "filename": access_log,
                "when": "D",
                "interval": 2,
                "backupCount": 30,
                "maxBytes": 10485760,
                "formatter": "access",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
            },
            "uvicorn.error": {
                "handlers": ["console", "app_file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "access_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)
