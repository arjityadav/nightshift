"""M4 · Chaos switches: break TinyShop on purpose, safely.   make check M=04"""

import logging
import os
import time

import pytest
from fastapi.testclient import TestClient

from tests.prom import sample
from tinyshop.api import create_app
from tinyshop.repository import InMemoryRepository

MUG = {"sku": "MUG-001", "name": "Mug", "price_cents": 1299, "stock": 10}
OFF = {"error_rate": 0, "latency_ms": 0, "leak_kb_per_request": 0, "leaked_kb": 0}


@pytest.fixture
def client():
    return TestClient(create_app(InMemoryRepository(), chaos_enabled=True))


def test_chaos_is_off_and_hidden_by_default():
    c = TestClient(create_app(InMemoryRepository()))
    assert c.get("/chaos").status_code == 404, "without chaos_enabled=True the /chaos routes must not exist"
    assert c.put("/chaos", json={"error_rate": 1}).status_code == 404
    assert c.delete("/chaos").status_code == 404
    assert c.post("/chaos/crash").status_code == 404


def test_initial_state(client):
    assert client.get("/chaos").json() == OFF


def test_settings_are_validated(client):
    for bad in (
        {"error_rate": 1.5},
        {"error_rate": -0.1},
        {"latency_ms": -1},
        {"latency_ms": 60_000},
        {"leak_kb_per_request": -1},
    ):
        assert client.put("/chaos", json=bad).status_code == 422, f"reject {bad}"


def test_put_replaces_the_whole_config(client):
    client.put("/chaos", json={"error_rate": 0.5, "latency_ms": 10})
    state = client.put("/chaos", json={"latency_ms": 20}).json()
    assert state["error_rate"] == 0 and state["latency_ms"] == 20, "PUT replaces; missing fields are 0"


def test_injected_errors(client, caplog):
    pid = client.post("/products", json=MUG).json()["id"]
    one = {"items": [{"product_id": pid, "quantity": 1}]}
    assert client.put("/chaos", json={"error_rate": 1}).status_code == 200
    caplog.set_level(logging.INFO, logger="tinyshop.access")

    r = client.post("/orders", json=one)
    assert r.status_code == 500 and r.json() == {"detail": "chaos: injected error"}
    assert client.get(f"/products/{pid}").json()["stock"] == 10, "an injected error must not change data"

    errors = [rec for rec in caplog.records if rec.name == "tinyshop.access" and rec.status == 500]
    assert errors and errors[0].levelno == logging.ERROR, "log 5xx responses at ERROR level"
    text = client.get("/metrics").text
    assert sample(text, "http_requests_total", method="POST", route="/orders", status="500") == 1, (
        "inject the error inside the /orders endpoint, so it is counted under route='/orders'"
    )

    assert client.delete("/chaos").json() == OFF
    assert client.post("/orders", json=one).status_code == 201


def test_latency_is_added_except_on_ops_endpoints(client):
    client.put("/chaos", json={"latency_ms": 300})
    start = time.perf_counter()
    client.get("/products")
    assert time.perf_counter() - start >= 0.29
    for path in ("/health", "/ready", "/metrics", "/chaos"):
        start = time.perf_counter()
        client.get(path)
        assert time.perf_counter() - start < 0.25, f"{path} must never be slowed down by chaos"


def test_injected_latency_is_measured(client):
    client.put("/chaos", json={"latency_ms": 300})
    client.get("/products")
    text = client.get("/metrics").text
    assert sample(text, "http_request_duration_seconds_sum", method="GET", route="/products") >= 0.29, (
        "start the timer BEFORE the chaos delay, or your dashboard can't see the latency you injected"
    )


def test_memory_leak(client):
    client.put("/chaos", json={"leak_kb_per_request": 100})
    for _ in range(3):
        client.get("/products")
    assert client.get("/chaos").json()["leaked_kb"] == 300, "/chaos itself must not leak"
    assert client.delete("/chaos").json() == OFF, "DELETE /chaos switches everything off and frees the leak"


def test_settings_are_exported_as_metrics(client):
    client.put("/chaos", json={"error_rate": 0.25, "latency_ms": 50})
    text = client.get("/metrics").text
    assert sample(text, "tinyshop_chaos", switch="error_rate") == 0.25
    assert sample(text, "tinyshop_chaos", switch="latency_ms") == 50
    assert sample(text, "tinyshop_chaos", switch="leak_kb_per_request") == 0
    client.delete("/chaos")
    assert sample(client.get("/metrics").text, "tinyshop_chaos", switch="error_rate") == 0


def test_crash_exits_after_responding(client, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "_exit", calls.append)
    r = client.post("/chaos/crash")
    assert r.status_code == 202
    assert calls == [1], "call os._exit(1) in a background task, so the response is sent first"
