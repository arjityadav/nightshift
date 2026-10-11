"""M4 · Structured JSON logs and request ids.   make check M=04"""

import json
import logging
import re
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from tinyshop.api import create_app
from tinyshop.logs import JsonFormatter, configure_logging
from tinyshop.repository import InMemoryRepository


def _format(**fields) -> dict:
    return json.loads(JsonFormatter().format(logging.makeLogRecord(fields)))


def test_one_json_object_per_line():
    line = JsonFormatter().format(logging.makeLogRecord({"name": "t", "levelname": "INFO", "msg": "hi"}))
    assert "\n" not in line, "one log record = one line (log shippers split on newlines)"
    assert isinstance(json.loads(line), dict)


def test_standard_fields():
    out = _format(name="tinyshop.test", levelname="WARNING", msg="stock low for %s", args=("MUG-001",))
    assert out["msg"] == "stock low for MUG-001", "use record.getMessage() so %s arguments are filled in"
    assert out["level"] == "WARNING"
    assert out["logger"] == "tinyshop.test"
    ts = datetime.fromisoformat(out["ts"])
    assert ts.tzinfo is not None, "timestamps must carry a time zone (UTC)"


def test_extra_fields_become_top_level_keys():
    out = _format(name="t", levelname="INFO", msg="request", request_id="abc123", status=200)
    assert out["request_id"] == "abc123"
    assert out["status"] == 200, "keep numbers as numbers, so LogQL can filter `status >= 500`"
    for internal in ("args", "levelno", "pathname", "lineno", "msecs", "relativeCreated", "thread"):
        assert internal not in out, f"don't dump LogRecord internals like {internal!r}"


def test_values_that_are_not_json_still_log():
    out = _format(name="t", levelname="INFO", msg="x", when=datetime(2026, 1, 1))
    assert "2026" in out["when"], "logging must never crash on an odd value: fall back to str()"


def test_exceptions_are_included_on_one_line():
    try:
        raise ZeroDivisionError("division by zero")
    except ZeroDivisionError:
        info = sys.exc_info()
    record = logging.makeLogRecord({"name": "t", "levelname": "ERROR", "msg": "boom", "exc_info": info})
    line = JsonFormatter().format(record)
    assert "\n" not in line, "the traceback goes inside the JSON string, not on extra lines"
    assert "ZeroDivisionError" in json.loads(line)["exc"]


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        configure_logging("DEBUG")
        configure_logging("DEBUG")
        json_handlers = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
        assert len(json_handlers) == 1, "calling configure_logging twice must not duplicate every line"
        assert root.level == logging.DEBUG
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


@pytest.fixture
def client():
    return TestClient(create_app(InMemoryRepository()))


def _access(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "tinyshop.access"]


def test_request_id_is_generated(client):
    first = client.get("/health").headers.get("x-request-id", "")
    assert re.fullmatch(r"[0-9a-f]{32}", first), "generate uuid4().hex when the client sends none"
    assert client.get("/health").headers["x-request-id"] != first


def test_incoming_request_id_is_reused(client):
    r = client.get("/health", headers={"X-Request-ID": "upstream-42"})
    assert r.headers["x-request-id"] == "upstream-42", "keep the caller's id so logs connect across services"


def test_unsafe_request_id_is_replaced(client):
    r = client.get("/health", headers={"X-Request-ID": "x" * 200})
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"]), (
        "never trust input: accept only short ids of letters, digits and '-', else generate one"
    )


def test_one_access_log_record_per_request(client, caplog):
    caplog.set_level(logging.INFO, logger="tinyshop.access")
    client.get("/products/999", headers={"X-Request-ID": "req-1"})
    records = _access(caplog)
    assert len(records) == 1, "log exactly one line per request on the logger 'tinyshop.access'"
    rec = records[0]
    assert rec.getMessage() == "request"
    assert rec.request_id == "req-1"
    assert rec.method == "GET" and rec.path == "/products/999"
    assert rec.route == "/products/{product_id}", "route = the matched route TEMPLATE"
    assert rec.status == 404
    assert isinstance(rec.duration_ms, int | float) and rec.duration_ms >= 0
    assert rec.levelno == logging.INFO, "4xx is the client's problem: INFO, not ERROR"


def test_unknown_paths_are_logged_as_unmatched(client, caplog):
    caplog.set_level(logging.INFO, logger="tinyshop.access")
    client.get("/does-not-exist")
    assert _access(caplog)[0].route == "unmatched"


def test_scrapes_are_not_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="tinyshop.access")
    client.get("/metrics")
    assert _access(caplog) == [], "Prometheus scrapes every few seconds: don't log /metrics"
