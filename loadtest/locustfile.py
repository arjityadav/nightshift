import random

from locust import HttpUser, between, task

PRODUCTS = [
    {"sku": f"LOAD-{i}", "name": f"Load test product {i}", "price_cents": 999, "stock": 1000}
    for i in range(1, 4)
]


class Shopper(HttpUser):
    wait_time = between(0.5, 2)  # each simulated user pauses 0.5–2 s between actions

    def on_start(self):
        """Runs once per simulated user: make sure the products exist, then remember their ids."""
        for product in PRODUCTS:
            with self.client.post("/products", json=product, catch_response=True, name="/products") as r:
                if r.status_code in (201, 409):  # 409 = created by an earlier user or run
                    r.success()
                else:
                    r.failure(f"unexpected {r.status_code}")
        self.product_ids = [p["id"] for p in self.client.get("/products").json()]

    @task(5)  # weight: browsing is 5× as frequent as stats, 2.5× as frequent as ordering
    def browse(self):
        self.client.get("/products")

    @task(2)
    def order(self):
        item = {"product_id": random.choice(self.product_ids), "quantity": 1}
        with self.client.post("/orders", json={"items": [item]}, catch_response=True, name="/orders") as r:
            if r.status_code in (201, 409):  # 409 = out of stock: expected, not a failure
                r.success()
            else:
                r.failure(f"unexpected {r.status_code}")

    @task(1)
    def stats(self):
        self.client.get("/stats/top-products")
