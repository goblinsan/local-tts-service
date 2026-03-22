from __future__ import annotations

import logging
import logging.config
import logging.handlers
import time
from pathlib import Path
from typing import Any


class TimeOrSizeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(
        self,
        filename: str,
        when: str = "D",
        interval: int = 2,
        backupCount: int = 5,
        encoding: str | None = "utf-8",
        delay: bool = False,
        utc: bool = False,
        atTime: Any | None = None,
        maxBytes: int = 10 * 1024 * 1024,
        maxArchiveBytes: int = 200 * 1024 * 1024,
        maxArchiveAgeDays: int = 10,
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
        self.maxArchiveBytes = maxArchiveBytes
        self.maxArchiveAgeDays = maxArchiveAgeDays

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

    def doRollover(self) -> None:
        super().doRollover()
        self._purge_archives()

    def _purge_archives(self) -> None:
        base_path = Path(self.baseFilename)
        if not base_path.exists() and not base_path.parent.exists():
            return

        archive_files = sorted(
            [
                path
                for path in base_path.parent.glob(f"{base_path.name}*")
                if path.is_file() and path.name != base_path.name
            ],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        if self.maxArchiveAgeDays > 0:
            cutoff_epoch = time.time() - (self.maxArchiveAgeDays * 24 * 60 * 60)
            for path in list(archive_files):
                try:
                    if path.stat().st_mtime < cutoff_epoch:
                        path.unlink(missing_ok=True)
                        archive_files.remove(path)
                except OSError:
                    continue

        if self.maxArchiveBytes <= 0:
            return

        total_size = 0
        for path in archive_files:
            try:
                total_size += path.stat().st_size
            except OSError:
                continue

        if total_size <= self.maxArchiveBytes:
            return

        for path in sorted(archive_files, key=lambda item: item.stat().st_mtime):
            if total_size <= self.maxArchiveBytes:
                break
            try:
                file_size = path.stat().st_size
                path.unlink(missing_ok=True)
                total_size -= file_size
            except OSError:
                continue


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
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
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
                "backupCount": 5,
                "maxBytes": 10485760,
                "maxArchiveBytes": 209715200,
                "maxArchiveAgeDays": 10,
                "formatter": "default",
                "encoding": "utf-8",
            },
            "access_file": {
                "()": "apps.api.logging_config.TimeOrSizeRotatingFileHandler",
                "filename": access_log,
                "when": "D",
                "interval": 2,
                "backupCount": 5,
                "maxBytes": 10485760,
                "maxArchiveBytes": 209715200,
                "maxArchiveAgeDays": 10,
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
