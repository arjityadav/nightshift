# Observability (metrics, logs, alerts, chaos)

## The three signals
- **Metrics**: numbers over time, cheap → alert on them. **Logs**: one line per event, detailed → investigate with them. **Traces**: time across services.
- A **request id** connects them: spike on a graph → find the failing requests in the logs.

## Python logging
- `Logger` (named, tree: `tinyshop.access` → `tinyshop` → root; records **propagate** up) → `LogRecord` → `Handler` (where) → `Formatter` (how).
- Levels: DEBUG < INFO < WARNING < ERROR < CRITICAL.
- `log.info("msg", extra={"status": 200})` sets `record.status`. `log.info()` is always INFO; to pick the level at runtime use `log.log(level, "msg", extra=...)`. The first argument of `.info()` is the **message**.
- **JSON formatter**: built-in fields = `set(vars(logging.makeLogRecord({})))`; everything else on the record came from `extra`. `json.dumps(..., default=str)` so logging never crashes; `"exc"` only when `record.exc_info`.
- `configure_logging` must be **idempotent**: remove only your own handler, then add it (pytest has its own handlers). Log to **stdout**: containers collect stdout.
- Call it in `main.py` before anything logs; level from `LOG_LEVEL` (config from the environment).

## Middleware, request ids, access log
- `@app.middleware("http")` wraps every request: before `await call_next(request)` → endpoint → after.
- Request id: reuse `X-Request-ID` only if `re.fullmatch(r"[A-Za-z0-9-]{1,64}", ...)` (log injection: never trust input), else `uuid.uuid4().hex`; return it in the response header.
- Route template after `call_next`: `request.scope.get("route")` → `.path` (`/products/{product_id}`), else `"unmatched"`.
- One access line per request on `tinyshop.access`: request_id, method, path, route, status, duration_ms; ERROR for ≥ 500. Skip `/metrics`.
- Durations: `time.perf_counter()` (monotonic), not `time.time()` (wall clock can jump). Keep milliseconds as float.
- Field names in logs are a contract (dashboards and LogQL depend on them).

## Interview questions

**Why structured (JSON) logs?**
<details><summary>Answer</summary>
Every field can be filtered and aggregated by tools (status >= 500, route, request_id) instead of regex on free text; one line per event; consistent across services.
</details>

**What is a request id for, and why validate an incoming one?**
<details><summary>Answer</summary>
It ties all log lines of one request together and across services (passed via X-Request-ID), and users can report it. It's untrusted input written into logs, so limit length and characters to prevent log injection and flooding.
</details>

**Why `time.perf_counter()` for durations?**
<details><summary>Answer</summary>
It's monotonic and high-resolution; `time.time()` follows the wall clock, which can jump (NTP, DST) and produce negative or wrong durations.
</details>
