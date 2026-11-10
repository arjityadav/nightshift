import json
import logging
import sys
from datetime import UTC, datetime

_STANDARD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Format each log record as one line of JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD:
                log_record[key] = value
        if record.exc_info:
            log_record["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_record, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send all logs to stdout as JSON. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h.formatter, JsonFormatter)]
    root.addHandler(handler)
    root.setLevel(level)
