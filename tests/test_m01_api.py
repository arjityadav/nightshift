"""M1 · The HTTP API with FastAPI.   make check M=01"""

import pytest
from fastapi.testclient import TestClient

from tinyshop.api import create_app
from tinyshop.repository import InMemoryRepository

MUG = {"sku": "MUG-001", "name": "Mug", "price_cents": 1299, "stock": 10}


@pytest.fixture
def client():
    return TestClient(create_app(InMemoryRepository()))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "version" in r.json()


def test_ready(client):
    assert client.get("/ready").status_code == 200


def test_ready_reports_a_broken_dependency():
    class BrokenRepo(InMemoryRepository):
        def ping(self):
            raise ConnectionError("database is down")

    r = TestClient(create_app(BrokenRepo())).get("/ready")
    assert r.status_code == 503


def test_create_and_get_product(client):
    r = client.post("/products", json=MUG)
    assert r.status_code == 201
    product = r.json()
    assert product["id"] >= 1 and product["sku"] == "MUG-001"
    assert client.get(f"/products/{product['id']}").json() == product


def test_validation_errors_are_422(client):
    assert client.post("/products", json=MUG | {"price_cents": -1}).status_code == 422
    assert client.post("/orders", json={"items": []}).status_code == 422


def test_duplicate_sku_is_409(client):
    client.post("/products", json=MUG)
    assert client.post("/products", json=MUG).status_code == 409


def test_unknown_ids_are_404(client):
    assert client.get("/products/999").status_code == 404
    assert client.get("/orders/999").status_code == 404
    assert client.post("/orders/999/cancel").status_code == 404
    r = client.post("/orders", json={"items": [{"product_id": 999, "quantity": 1}]})
    assert r.status_code == 404
    assert "detail" in r.json()


def test_list_products_pagination(client):
    for i in range(3):
        client.post("/products", json=MUG | {"sku": f"MUG-00{i}"})
    assert len(client.get("/products").json()) == 3
    assert [p["sku"] for p in client.get("/products?limit=1&offset=1").json()] == ["MUG-001"]
    assert client.get("/products?limit=0").status_code == 422
    assert client.get("/products?limit=101").status_code == 422


def test_order_flow(client):
    pid = client.post("/products", json=MUG | {"stock": 2}).json()["id"]
    r = client.post("/orders", json={"items": [{"product_id": pid, "quantity": 2}]})
    assert r.status_code == 201
    order = r.json()
    assert order["total_cents"] == 2598 and order["status"] == "created"
    assert client.get(f"/orders/{order['id']}").json()["id"] == order["id"]

    sold_out = client.post("/orders", json={"items": [{"product_id": pid, "quantity": 1}]})
    assert sold_out.status_code == 409

    cancelled = client.post(f"/orders/{order['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.get(f"/products/{pid}").json()["stock"] == 2
    assert client.post(f"/orders/{order['id']}/cancel").status_code == 409


def test_top_products(client):
    pid = client.post("/products", json=MUG).json()["id"]
    client.post("/orders", json={"items": [{"product_id": pid, "quantity": 2}]})
    assert client.get("/stats/top-products").json() == [{"sku": "MUG-001", "revenue_cents": 2598}]


def test_openapi_docs_exist(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "TinyShop"
    assert "/orders" in spec["paths"]
