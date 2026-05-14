from __future__ import annotations
import logging
import json
import os
from datetime import datetime, timezone

from ..config import settings

logger = logging.getLogger(__name__)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def setup_json_logging():
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) or isinstance(handler, logging.FileHandler):
            handler.setFormatter(JSONFormatter())


def setup_sentry():
    dsn = os.environ.get("SENTRY_DSN", "")
    if dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=dsn,
                environment=os.environ.get("ENV", "development"),
                traces_sample_rate=0.1,
            )
            logger.info(f"[Sentry] SDK inicializado")
        except Exception as e:
            logger.debug(f"[Sentry] Nao configurado: {e}")
