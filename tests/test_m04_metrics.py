"""M4 · Prometheus metrics: RED for every route, plus one business metric.   make check M=04"""

import pytest
from fastapi.testclient import TestClient

from tests.prom import sample
from tinyshop.api import create_app
from tinyshop.repository import InMemoryRepository

MUG = {"sku": "MUG-001", "name": "Mug", "price_cents": 1299, "stock": 10}


@pytest.fixture
def client():
    return TestClient(create_app(InMemoryRepository()))


def scrape(client) -> str:
    r = client.get("/metrics")
    assert r.status_code == 200, "add GET /metrics"
    assert r.headers["content-type"].startswith("text/plain"), "use prometheus_client.CONTENT_TYPE_LATEST"
    return r.text


def test_requests_are_counted_by_route_template(client):
    client.post("/products", json=MUG)
    client.get("/products/1")
    client.get("/products/1")
    client.get("/products/999")
    text = scrape(client)
    counted = "http_requests_total"
    assert sample(text, counted, method="POST", route="/products", status="201") == 1
    assert sample(text, counted, method="GET", route="/products/{product_id}", status="200") == 2
    assert sample(text, counted, method="GET", route="/products/{product_id}", status="404") == 1
    assert 'route="/products/1"' not in text, "label with the route TEMPLATE, never the raw path"


def test_unknown_paths_share_one_label(client):
    client.get("/does-not-exist")
    client.get("/also/missing/42")
    text = scrape(client)
    assert sample(text, "http_requests_total", method="GET", route="unmatched", status="404") == 2, (
        "every unknown path must map to route='unmatched', or scanners create endless time series"
    )


def test_latency_histogram(client):
    for _ in range(3):
        client.get("/health")
    text = scrape(client)
    hist = "http_request_duration_seconds"
    assert sample(text, f"{hist}_count", method="GET", route="/health") == 3
    assert sample(text, f"{hist}_bucket", method="GET", route="/health", le="+Inf") == 3
    assert sample(text, f"{hist}_sum", method="GET", route="/health") >= 0


def test_scrapes_are_not_counted(client):
    scrape(client)
    text = scrape(client)
    assert 'route="/metrics"' not in text, "don't measure the scrapes themselves"


def test_in_progress_gauge_returns_to_zero(client):
    client.get("/health")
    client.get("/nope")
    assert sample(scrape(client), "http_requests_in_progress") == 0, (
        "increase before the request, decrease after it, even when it fails (try/finally)"
    )


def test_orders_business_metric(client):
    pid = client.post("/products", json=MUG | {"stock": 1}).json()["id"]
    one = {"items": [{"product_id": pid, "quantity": 1}]}
    assert client.post("/orders", json=one).status_code == 201
    assert client.post("/orders", json=one).status_code == 409
    assert client.post("/orders", json={"items": [{"product_id": 999, "quantity": 1}]}).status_code == 404
    text = scrape(client)
    assert sample(text, "tinyshop_orders_total", result="created") == 1
    assert sample(text, "tinyshop_orders_total", result="out_of_stock") == 1
    assert sample(text, "tinyshop_orders_total", result="not_found") == 1


def test_each_app_has_its_own_registry():
    a = TestClient(create_app(InMemoryRepository()))
    b = TestClient(create_app(InMemoryRepository()))  # must not fail with "Duplicated timeseries"
    a.get("/health")
    assert sample(scrape(b), "http_requests_total", route="/health") is None, (
        "give each app its own CollectorRegistry instead of the global default one"
    )
