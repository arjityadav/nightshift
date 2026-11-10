# M4 · Observability and chaos

**Time:** ~1.5 weeks · **Tests:** `make check M=04` · **You'll have:** TinyShop that reports metrics and JSON logs, a local Prometheus + Loki + Grafana stack with alerts, a load generator, and **chaos switches** to break TinyShop on purpose and watch it happen.

Nightshift will investigate incidents the way an SRE does: by reading metrics and logs. Before it can do that, TinyShop has to *produce* good signals, and you have to learn to read them yourself. In this module you break TinyShop in five different ways and learn what each failure looks like. These scenarios become Nightshift's evaluation set later (M8, M12).

---

## Concepts

### Metrics, logs and traces

| Signal | Answers | Example | Cost |
|---|---|---|---|
| **Metrics** | "how much / how fast / how many, over time?" | 3 % of `/orders` requests failed in the last 5 minutes | tiny: numbers, aggregated |
| **Logs** | "what exactly happened in *this* request?" | `request_id=7f3a… POST /orders 500 "chaos: injected error"` | bigger: one line per event |
| **Traces** | "where did the time go across services?" | the request spent 480 ms in the database | biggest; for many services (not in this course) |

You **alert on metrics** (cheap, fast to query) and **investigate with logs** (detailed). A request id connects the two: you see an error spike on a graph, then find the exact failing requests in the logs.

### The four metric types

| Type | Behaviour | Use for | TinyShop |
|---|---|---|---|
| **Counter** | only goes up (resets to 0 on restart) | things that happen | `http_requests_total`, `tinyshop_orders_total` |
| **Gauge** | goes up and down | current state | `http_requests_in_progress`, memory, chaos settings |
| **Histogram** | counts observations into buckets (≤ 5 ms, ≤ 10 ms, … ≤ 10 s) | durations, sizes | `http_request_duration_seconds` |
| **Summary** | calculates quantiles inside the app | rarely; histograms can be combined across instances, summaries can't | none |

A counter's raw value ("1,284,113 requests since start") is useless by itself. What matters is how fast it grows: `rate(http_requests_total[1m])` = requests **per second**, averaged over the last minute. Restarts are handled for you: `rate()` notices the reset to 0.

**Why a histogram and not an average?** Averages hide pain. If 95 requests take 10 ms and 5 take 2 s, the average is 110 ms ("fine!"), but 1 user in 20 waits 2 seconds. The **p95** (95th percentile: 95 % of requests are faster than this) shows it. `histogram_quantile(0.95, …)` estimates it from the buckets.

### Labels and cardinality

Labels split one metric into several **time series**: `http_requests_total{method="GET", route="/products/{product_id}", status="200"}`. Every distinct combination of label values is a separate series that Prometheus stores and queries.

**Cardinality** is the number of series. Labelling with the raw path (`/products/1`, `/products/2`, … `/products/999999`) creates one series per product, and a scanner hitting random URLs creates millions. That's the classic way to take down a Prometheus server. So:
- label with the **route template** (`/products/{product_id}`), never the raw path;
- map every unknown path to one value (`route="unmatched"`);
- never use ids, emails or request ids as labels. They belong in **logs**.

### RED and USE

Two checklists for "what should I measure?":
- **RED** for every *service*: **R**ate (requests/s), **E**rrors (failed requests/s), **D**uration (latency distribution). Your HTTP metrics cover all three.
- **USE** for every *resource* (CPU, memory, disk, connections): **U**tilisation, **S**aturation (work waiting), **E**rrors.

### Prometheus: pull, store, query, alert

Prometheus **pulls** (scrapes) `GET /metrics` from every target every few seconds, stores the numbers as time series, and evaluates **alert rules** on them. Pull means the app doesn't need to know where Prometheus is, and a target that stops answering is itself a signal: Prometheus sets `up{job="tinyshop"}` to 0.

PromQL you'll use all the time:
```promql
up{job="tinyshop"}                                                        # 1 = scrape worked
sum by (route) (rate(http_requests_total[1m]))                            # requests/s per route
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))                                    # 5xx ratio (0.02 = 2 %)
histogram_quantile(0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))    # p95 latency per route
```
`[5m]` is a **range**: "the samples of the last 5 minutes". `sum by (route)` adds the series up but keeps `route` apart. `le` ("less or equal") is the bucket label of a histogram, and `histogram_quantile` needs it, so always keep `le` in the `by (…)`.

### Structured logs and request ids

A plain log line (`Order failed for product 7`) is easy to read and hard to search. A **JSON** line is both:
```json
{"ts": "2026-10-11T09:14:03.120+00:00", "level": "ERROR", "logger": "tinyshop.access", "msg": "request",
 "request_id": "7f3a9c…", "method": "POST", "route": "/orders", "status": 500, "duration_ms": 12.4}
```
Every field can be filtered and counted. The **request id** is generated once per request (or taken from the caller's `X-Request-ID` header, so ids connect across services), put on every log line of that request, and returned in the response header, so a user's bug report ("it failed, here's the id") leads straight to the logs.

### Loki and LogQL

**Loki** stores log lines, indexed only by a few **labels** (here `service="api"`), not by their content. That keeps it cheap. **Grafana Alloy** reads each container's output and ships it to Loki. **LogQL** first selects streams by label, then filters and parses lines:
```logql
{service="api"}                                    # all api lines
{service="api"} |= "ERROR"                         # lines containing ERROR
{service="api"} | json | status >= 500             # parse JSON, filter on a field
{service="api"} | json | request_id = "7f3a9c…"    # one request's story
sum by (route) (count_over_time({service="api"} | json | status >= 500 [5m]))   # logs → numbers
```
Same cardinality rule as Prometheus: few labels (`service`), everything else as fields in the line.

### SLIs, SLOs and error budgets

- **SLI** (indicator): a measured ratio that reflects user happiness, e.g. *the share of requests that don't fail with 5xx*, or *the share of requests faster than 500 ms*.
- **SLO** (objective): the target for that SLI over a window, e.g. *99.5 % of requests succeed over 30 days*.
- **Error budget**: what the SLO allows to fail. 0.5 % of requests, or about 3.6 hours of full outage per 30 days. While budget is left, the team can ship risky changes. When it's spent, reliability work comes first.

**Alert on symptoms users feel** (error ratio, latency, service down), not on causes (CPU at 80 %). Every alert has a `for:` duration, so one bad scrape or a 10-second blip doesn't wake anyone: it must stay true for, say, a minute. In M13 you'll replace these simple alerts with **burn-rate** alerts on the error budget.

### Chaos engineering

Breaking things on purpose, **as an experiment**: state a hypothesis ("if 20 % of orders fail, the error alert fires within 2 minutes and the logs show which requests failed"), inject the fault, observe, compare, switch it off. The safety rules matter as much as the faults:
- **off by default and impossible in production**: the `/chaos` routes only exist when `CHAOS_ENABLED=true`, which you set only in your local `compose.yaml`;
- **small blast radius**: one switch at a time, with a known way back (`DELETE /chaos` turns everything off);
- **never break the tools you need to recover**: `/health`, `/ready`, `/metrics` and `/chaos` itself are never slowed down or broken.

Each switch imitates a real incident from the blueprint's list: `error_rate` (bad deploy), `latency_ms` (slow dependency), `leak_kb_per_request` (memory leak → OOMKilled), `POST /chaos/crash` (crash → restart). The current settings are exported as a metric (`tinyshop_chaos`), so later you always know **the ground truth**: what was really broken, and when. That's what makes Nightshift measurable.

---

## Step 1 · Branch and dependency

```bash
git switch main && git pull
git switch -c m04-observability      # if you haven't yet
uv add prometheus-client
```
`prometheus-client` is a runtime dependency (the app serves `/metrics`). Locust, the load tester, is **not** added: you'll run it with `uvx`, which downloads a tool into a temporary environment, so it never touches your lock file.

The tests import `tinyshop.logs`, `tinyshop.metrics` and `prometheus_client`, so `make check M=04` shows collection errors until the files exist. As in M0, create the modules first (even almost empty), then work test by test.

## Step 2 · JSON logs: `tinyshop/logs.py`

```python
class JsonFormatter(logging.Formatter):
    """Format a LogRecord as ONE line of JSON:
    {"ts": <ISO 8601 in UTC, with offset>, "level": "INFO", "logger": "tinyshop.access",
     "msg": <record.getMessage()>, ...every `extra` field as a top-level key...,
     "exc": <formatted traceback, only if there is one>}
    Values that aren't JSON (datetime, Decimal, ...) are written with str()."""


def configure_logging(level: str = "INFO") -> None:
    """Send all logs to stdout as JSON at `level`. Calling it twice must not add a second handler."""
```
How `extra` works: `log.info("request", extra={"status": 200})` sets `record.status = 200`. A LogRecord already has ~20 built-in attributes (`args`, `levelno`, `pathname`, …) that you must *not* dump. One way to know which attributes are built in: `set(vars(logging.makeLogRecord({})))`.

<details>
<summary>Hints</summary>

- Time: `datetime.fromtimestamp(record.created, UTC).isoformat()`.
- JSON that never crashes: `json.dumps(data, default=str)`.
- Tracebacks: `self.formatException(record.exc_info)` gives a multi-line string. `json.dumps` escapes the newlines, so it stays one line.
- Idempotent: remove your previous JSON handler (check `isinstance(handler.formatter, JsonFormatter)`) before adding the new one. Don't remove handlers you didn't create: pytest has its own.
- Uvicorn configures its own loggers (`uvicorn`, `uvicorn.error`) with plain-text handlers. To make them JSON too, clear their handlers and set `propagate = True`, so their records reach your root handler.
</details>

**Why stdout?** In containers, the platform collects stdout (Docker, Kubernetes, Alloy). An app that writes log files inside a container makes its logs disappear with the container.

## Step 3 · Request ids and the access log

Add **one HTTP middleware** to `create_app`. A middleware wraps every request:
```python
@app.middleware("http")
async def timing(request: Request, call_next):          # an example, not TinyShop's
    start = time.perf_counter()
    response = await call_next(request)                 # runs routing, the endpoint, exception handlers
    response.headers["X-Elapsed-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response
```
Yours must:
1. **Request id:** take `X-Request-ID` from the request if it's safe (1–64 characters of `A–Z a–z 0–9 -`), otherwise generate `uuid.uuid4().hex`. Return it in the response header `X-Request-ID`.
2. **Access log:** after the response, log **one** record on the logger `tinyshop.access`, message `"request"`, with `extra` fields `request_id`, `method`, `path` (the raw path), `route`, `status` (int) and `duration_ms` (float). Level **ERROR** for status ≥ 500, otherwise **INFO**. Skip `/metrics`.
3. **Route template:** after `call_next`, the matched route is in `request.scope.get("route")`; its `.path` is the template (`/products/{product_id}`). No route (unknown path) → `"unmatched"`.

**Why validate the incoming id?** It's user input that goes straight into your logs. A 10 MB header or one with newlines and fake JSON could flood or forge log lines (*log injection*). Never trust input, even "just an id".

**If the endpoint raises an unexpected exception**, `call_next` raises too. Use `try/finally` so the request is still logged and counted (as status 500), then let the exception continue.

## Step 4 · Metrics: `tinyshop/metrics.py` and `GET /metrics`

| Name | Type | Labels | Meaning |
|---|---|---|---|
| `http_requests_total` | Counter | `method`, `route`, `status` | finished requests |
| `http_request_duration_seconds` | Histogram | `method`, `route` | request duration |
| `http_requests_in_progress` | Gauge | none | requests being handled right now |
| `tinyshop_orders_total` | Counter | `result`: `created`, `out_of_stock`, `not_found` | order outcomes (a business metric) |
| `tinyshop_chaos` | Gauge | `switch`: `error_rate`, `latency_ms`, `leak_kb_per_request` | current chaos settings (Step 5) |

Write a small class that creates these with **its own** `CollectorRegistry`:
```python
from prometheus_client import CollectorRegistry, Counter

registry = CollectorRegistry()
books_sold = Counter("books_sold_total", "Books sold", ["genre"], registry=registry)
books_sold.labels("fantasy").inc()
```
Create one instance in `create_app` (store it on `app.state`, like the repository). The default global registry would break as soon as two apps exist in one process. Your tests create dozens, so you'd get `Duplicated timeseries in CollectorRegistry`. It's the same lesson as the app factory in M1: no global state.

Also register `ProcessCollector(registry=...)` (from `prometheus_client`). It adds `process_resident_memory_bytes` and CPU time, which you need for the memory leak. It only works on Linux, so you'll see it in the container, not with `make run` on a Mac.

Then:
- **`GET /metrics`** returns `generate_latest(registry)` with `media_type=CONTENT_TYPE_LATEST`. Don't count or log scrapes.
- In the middleware: increase `in_progress` before the request, decrease it in `finally`; after the response, increase the counter and observe the duration, both labelled with the **route template**.
- In `POST /orders`: count the outcome. Catch `OutOfStockError` / `NotFoundError` only to count them, then `raise` again so your M1 exception handlers still turn them into 409 / 404.

Try it: `make run`, click around in `/docs`, open `localhost:8000/metrics` and find your series.

## Step 5 · Chaos switches: `tinyshop/chaos.py`

`create_app(repo, *, chaos_enabled: bool = False)`. The `*` makes `chaos_enabled` keyword-only, so `create_app(repo, True)` is an error and every call says what it means.

```python
class ChaosConfig(BaseModel):
    error_rate: float           # 0–1: share of POST /orders that fail with 500
    latency_ms: int             # 0–10000: extra delay on every non-ops request
    leak_kb_per_request: int    # 0–10240: memory kept forever on every non-ops request
```
All fields default to 0 (off). The chaos **state** (the current config plus the leaked memory) always exists inside `create_app`. Only the **control routes** depend on `chaos_enabled`. When it's `False`, they don't exist at all (404):

| Route | Does | Returns |
|---|---|---|
| `GET /chaos` | current state | `{"error_rate", "latency_ms", "leak_kb_per_request", "leaked_kb"}` |
| `PUT /chaos` | **replaces** the config (validated, 422 on bad values) | the new state |
| `DELETE /chaos` | everything off, leaked memory freed | the state (all 0) |
| `POST /chaos/crash` | answers **202**, then the process exits | `{"status": "crashing"}` |

How each switch works:
- **Ops paths** (`/health`, `/ready`, `/metrics` and everything under `/chaos`) are never touched by chaos.
- **Latency** goes in the middleware: `await asyncio.sleep(seconds)`. **Never `time.sleep()` in async code**: it blocks the event loop, and *every* request in the process waits, not just this one. Start your duration timer *before* the sleep, or your dashboard won't see the latency you injected (there's a test for this).
- **Leak** goes in the middleware: append `b"x" * (kb * 1024)` to a list that lives as long as the app. (`b"x" * n` really writes the memory. A zero-filled `bytearray(n)` may not count in RSS until it's touched.)
- **Errors** go **inside the `POST /orders` endpoint**, before calling the repository: `if random.random() < error_rate:` raise a small `ChaosError`, and map it to 500 `{"detail": "chaos: injected error"}` with an exception handler. Inside the endpoint, the request is counted under `route="/orders"`, and no stock changes.
- **Crash**: add a background task (`BackgroundTasks`, a FastAPI parameter) that calls `os._exit(1)`. It runs *after* the response is sent. `os._exit` ends the process immediately, like a segfault or the kernel's OOM killer would. `sys.exit()` would only raise an exception that the server catches.
- **Metric**: after every `PUT`/`DELETE` (and once at startup), set `tinyshop_chaos{switch=...}` to each value.

Wire it in `main.py`:
```python
configure_logging(os.environ.get("LOG_LEVEL", "INFO"))     # before anything logs (migrations too)
app = create_app(build_repository(os.environ), chaos_enabled=<CHAOS_ENABLED is "true">)
```

Run `make check M=04`: logging, metrics and chaos tests should be green now. The stack tests come next.

## Step 6 · The observability stack in Compose

Turn off uvicorn's own plain-text access log, since your middleware logs every request as JSON. In the `Dockerfile` `CMD`, add `"--no-access-log"` to the list.

In `compose.yaml`, add to the `api` service:
```yaml
    environment:
      DATABASE_URL: ...                       # as before
      CHAOS_ENABLED: "true"                   # local stack only, never in staging/prod
    mem_limit: 300m                           # so the memory leak ends in an OOM kill, like in Kubernetes
```
And four new services:
```yaml
  prometheus:
    image: prom/prometheus:v3.15.0
    command: ["--config.file=/etc/prometheus/prometheus.yml", "--web.enable-lifecycle"]
    volumes:
      - ./deploy/prometheus:/etc/prometheus:ro
    ports:
      - "9090:9090"

  loki:
    image: grafana/loki:3.7.8                 # its default config stores logs on local disk: fine for a laptop
    ports:
      - "3100:3100"

  alloy:
    image: grafana/alloy:v1.20.1
    command: ["run", "--server.http.listen-addr=0.0.0.0:12345", "--storage.path=/var/lib/alloy/data",
              "/etc/alloy/config.alloy"]
    volumes:
      - ./deploy/alloy/config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro     # to read the other containers' logs
    ports:
      - "12345:12345"                                    # Alloy's own UI: shows its pipeline

  grafana:
    image: grafana/grafana:13.2.3
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"       # local only: no login screen
      GF_AUTH_ANONYMOUS_ORG_ROLE: Admin
    volumes:
      - ./deploy/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./deploy/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
    depends_on: [prometheus, loki]
```
**The Docker socket is powerful:** whoever can talk to it controls every container on the machine, which is effectively root. Mounting it read-only into a log collector on your laptop is acceptable. In Kubernetes (M6), Alloy reads log files from the nodes instead.

**Prometheus**: create `deploy/prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 5s          # often, so experiments show up fast (production: 15–60 s)
  evaluation_interval: 5s

rule_files:
  - alerts.yml

scrape_configs:
  - job_name: tinyshop
    static_configs:
      - targets: ["api:8000"]   # the Compose service name, like `db` in M3
```

**Alerts**: create `deploy/prometheus/alerts.yml`. The first rule is given; write the other two yourself:
```yaml
groups:
  - name: tinyshop
    rules:
      - alert: TinyShopDown
        expr: up{job="tinyshop"} == 0
        for: 30s
        labels:
          severity: page
        annotations:
          summary: "Prometheus can't scrape TinyShop"
```
- **`TinyShopHighErrorRate`**: the 5xx ratio over `[1m]` is above 5 %, for 1 minute.
- **`TinyShopHighLatency`**: p95 latency over `[1m]` (all routes together: `sum by (le)`) is above 0.5 s, for 1 minute.

Both get `labels: severity: page` and a `summary`. Test your expressions in the Prometheus UI (**localhost:9090 → Query**) before putting them in the file. After editing rules: `curl -X POST localhost:9090/-/reload` (that's what `--web.enable-lifecycle` allows).

**Alloy** (given): create `deploy/alloy/config.alloy`:
```alloy
// Find the containers of this Compose project through the Docker socket.
discovery.docker "nightshift" {
  host = "unix:///var/run/docker.sock"

  filter {
    name   = "label"
    values = ["com.docker.compose.project=nightshift"]
  }
}

// Turn Docker metadata into Loki labels: the Compose service name becomes `service`.
discovery.relabel "nightshift" {
  targets = []

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }
}

// Read each container's output and forward the lines.
loki.source.docker "nightshift" {
  host          = "unix:///var/run/docker.sock"
  targets       = discovery.docker.nightshift.targets
  relabel_rules = discovery.relabel.nightshift.rules
  forward_to    = [loki.write.local.receiver]
}

// Push to Loki.
loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```
Alloy configs are **pipelines**: each block is a component, and `forward_to` connects them. The filter keeps your other Compose projects out of Loki. The project name defaults to the folder name, `nightshift`.

**Grafana data sources** (given): `deploy/grafana/provisioning/datasources/datasources.yml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
  - name: Loki
    type: loki
    uid: loki
    access: proxy
    url: http://loki:3100
```
**Dashboard provider** (given): `deploy/grafana/provisioning/dashboards/dashboards.yml`:
```yaml
apiVersion: 1
providers:
  - name: tinyshop
    folder: TinyShop
    type: file
    options:
      path: /var/lib/grafana/dashboards
```
*Provisioning* means Grafana's setup lives in files in Git, not in clicks that get lost when the container is recreated. It's "configuration as code", the same idea as migrations.

Start everything and check each piece:
```bash
mkdir -p deploy/grafana/dashboards
make up
docker compose ps                                # 6 services running
open http://localhost:9090/targets               # tinyshop: UP
open http://localhost:9090/alerts                # your three rules, "inactive"
open http://localhost:12345                      # Alloy: the pipeline is green
open http://localhost:3000                       # Grafana → Explore → Loki: {service="api"}
```
(`open` is macOS; on Linux/WSL, paste the URLs into your browser.)

## Step 7 · Load: `loadtest/locustfile.py`

Graphs of an idle service are flat. Locust simulates users:
```python
import random

from locust import HttpUser, between, task


class Shopper(HttpUser):
    wait_time = between(0.5, 2)       # each simulated user pauses 0.5–2 s between actions

    @task(5)                          # weight: browsing is 5× as frequent as ...
    def browse(self):
        self.client.get("/products")
```
Add yourself:
- an `on_start(self)` method that makes sure a few products exist (POST them; a 409 just means they're already there);
- a **weight-2 task that places an order** for a random product. Use `catch_response=True` and mark **201 and 409 as success**: running out of stock is expected business behaviour, not a failure of the system. Only 5xx should count as failures in Locust's report. Give it `name="/orders"` so Locust groups the requests the same way your `route` label does;
- a weight-1 task for `GET /stats/top-products`.

Makefile (TAB!):
```makefile
load:               ## 2 minutes of traffic: 20 users, 5 new per second
	uvx locust -f loadtest/locustfile.py --headless -u 20 -r 5 -t 2m --host http://localhost:8000
```
Without `--headless`, Locust opens a web UI at localhost:8089 where you can change the number of users live.

## Step 8 · Build the dashboard

In Grafana: **Dashboards → New → New dashboard → Add visualization**. Build these panels (`make load` running in another terminal, so you can see data). Query editor → **Code** mode for typing PromQL:

| Panel | Query |
|---|---|
| Requests/s by route | `sum by (route) (rate(http_requests_total[1m]))` |
| 5xx ratio | your error-rate expression, unit *Percent (0.0–1.0)* |
| p95 latency by route | `histogram_quantile(0.95, sum by (le, route) (rate(http_request_duration_seconds_bucket[1m])))`, unit *seconds* |
| In progress | `http_requests_in_progress` |
| Memory | `process_resident_memory_bytes{job="tinyshop"}`, unit *bytes* |
| Orders by result | `sum by (result) (rate(tinyshop_orders_total[1m]))` |
| Chaos switches | `tinyshop_chaos`, legend `{{switch}}` |
| Error logs (data source Loki, visualization *Logs*) | `{service="api"} \| json \| status >= 500` |

Then **Export → Export as JSON → Download**, and save the file as `deploy/grafana/dashboards/tinyshop.json`. After `docker compose restart grafana` it's provisioned from Git, in the folder *TinyShop*. Provisioned dashboards can't be saved from the UI. To change one: edit, export again, replace the file.

## Step 9 · Break it on purpose

Keep `make load` running, the dashboard open (time range *Last 15 minutes*, refresh *5s*), and do **one experiment at a time**. For each one, first write down what you **expect** (hypothesis), then compare it with what you see. Turn everything off afterwards with `curl -X DELETE localhost:8000/chaos`.
```bash
chaos() { curl -s -X PUT localhost:8000/chaos -H 'content-type: application/json' -d "$1"; echo; }
```

| # | Inject | Expect to see |
|---|---|---|
| 1 | `chaos '{"error_rate": 0.2}'` | 5xx ratio ~20 % on `/orders` only; `TinyShopHighErrorRate` **pending**, then **firing** after 1 min; ERROR lines in the logs panel. Copy one `request_id` and find that request in Explore. |
| 2 | `chaos '{"latency_ms": 800}'` | p95 jumps for every non-ops route; `TinyShopHighLatency` fires; Locust's response times jump too |
| 3 | `chaos '{"leak_kb_per_request": 512}'` | memory climbs in steps until ~300 MB, the container is **OOM-killed** and restarts: `docker inspect nightshift-api-1 --format '{{.State.OOMKilled}} {{.RestartCount}}'`; memory drops to normal, and `up` dips |
| 4 | `curl -X POST localhost:8000/chaos/crash` | `up` drops to 0 for a few seconds, Compose restarts the container (`restart: unless-stopped`), `docker compose ps` shows a fresh uptime; a short `TinyShopDown` pending |
| 5 | `docker compose stop db` (then `start db`) | `/ready` → 503, orders → 500 (the database error isn't a domain error: why is 500 correct here?), connection errors in the logs |
| 6 | **slow query**, for real: the 200,000 orders below | p95 rises for `route="/stats/top-products"` only, every other route stays fast. Compare with experiment 2, where *every* route got slow. The `route` label tells you **where** to look. |
| 7 | **a harmless blip**: `chaos '{"error_rate": 0.5}'`, wait 15 s, `curl -X DELETE …/chaos` | the error graph spikes, the alert goes **pending** but never **firing**, thanks to `for: 1m`. Nobody gets paged. |

Data for experiment 6 (in `docker compose exec db psql -U tinyshop -d tinyshop`). It takes a few seconds:
```sql
INSERT INTO products (sku, name, price_cents, stock)
  SELECT 'BULK-' || g, 'Bulk ' || g, 100 + g, 1000000 FROM generate_series(1, 50) AS g
  ON CONFLICT (sku) DO NOTHING;
INSERT INTO orders (total_cents, created_at)
  SELECT 100, now() - g * interval '1 minute' FROM generate_series(1, 200000) AS g;
WITH ids AS (SELECT array_agg(id) AS a FROM products)
INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
  SELECT o.id, ids.a[1 + o.id % array_length(ids.a, 1)], 1, 100
  FROM orders o, ids
  WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.id);
ANALYZE;
```
Then `EXPLAIN ANALYZE` the `top_products` query: where does the time go? (Undo it with `docker compose down -v`, which deletes the data volume.)

Write what you saw for each experiment (graph, alert, log line, time until the alert fired) into your notes. That table is your first **incident dataset**, and in M8 and M12 Nightshift has to find these causes on its own.

---

## Definition of done

- [ ] `make check M=04` is green, and `make test` + `make test-db` are still green.
- [ ] `make up` starts api, db, prometheus, loki, alloy and grafana; the target is UP; the dashboard is provisioned from `deploy/grafana/dashboards/tinyshop.json`.
- [ ] You ran all seven experiments under `make load` and wrote down what you saw; at least the error-rate and latency alerts reached **firing**.
- [ ] You found all log lines of one failed request in Loki by its `request_id`.
- [ ] A screenshot of the dashboard during an experiment (for your README later).
- [ ] Committed and pushed in small steps; PR "M4: Observability and chaos" merged.

## Interview questions

1. **Counter, gauge, histogram: when do you use which?** Counter for things that happen (requests, errors), always read with `rate()`; gauge for current values (memory, queue length, in-flight requests); histogram for distributions like latency, so you can compute percentiles and aggregate them across instances.
2. **Why p95/p99 instead of the average latency?** Averages hide the slow tail; the p95 says what the slowest 5 % of users experience. Percentiles from histograms can be aggregated across instances; averages of percentiles can't.
3. **What is label cardinality and how do you keep it under control?** Each label combination is a time series. Use bounded values only: route templates, status codes, a fixed set of results. Never ids, paths or emails, which belong in logs. Map unknown paths to one value.
4. **RED and USE?** RED (rate, errors, duration) for services, USE (utilisation, saturation, errors) for resources.
5. **Why structured logs and request ids?** Machine-filterable fields (`status >= 500`, `route`), one line per event, and a request id that connects all lines of one request, the response the user saw, and other services.
6. **Pull (Prometheus) vs push?** Pull: the server controls scrape rate, finds targets by service discovery, and a dead target is visible (`up == 0`). Push suits short batch jobs (Pushgateway) and some SaaS backends.
7. **SLI, SLO, error budget?** SLI = a measured ratio users care about; SLO = its target over a window; error budget = 1 − SLO, the failure you can afford. It balances shipping speed against reliability.
8. **What makes a good alert?** It's about a symptom users feel, it's actionable, it has a `for:` so blips don't page, and it links a runbook. Causes (high CPU) go on dashboards, not pagers.
9. **How do you run chaos experiments safely?** Hypothesis first, smallest blast radius, off by default and impossible in production, a tested way back (`DELETE /chaos`), never break the tools you need to observe and recover.
10. **Why must you never call `time.sleep()` in an async FastAPI middleware?** It blocks the event loop thread, so every concurrent request waits; `await asyncio.sleep()` yields to other requests.

**Next:** M5 · CI with GitHub Actions: every push runs lint, tests against a real PostgreSQL, builds the image, scans it and pushes it to GHCR. (Ask for the M5 lesson when you're here.)
