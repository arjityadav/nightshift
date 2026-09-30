"""Behaviour EVERY repository must have (in-memory in M1, PostgreSQL in M3).

This is a "contract test": one set of tests, run against several implementations.
(Given: you don't need to change this file.)
"""

import pytest

from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import OrderIn, ProductIn


def product(sku="MUG-001", name="Mug", price_cents=1299, stock=10):
    return ProductIn(sku=sku, name=name, price_cents=price_cents, stock=stock)


def order(*items):
    return OrderIn(items=[{"product_id": pid, "quantity": qty} for pid, qty in items])


class RepositoryContract:
    def make_repo(self):
        raise NotImplementedError

    @pytest.fixture
    def repo(self):
        return self.make_repo()

    def test_add_and_get_product(self, repo):
        p = repo.add_product(product())
        assert p.id >= 1 and p.sku == "MUG-001" and p.stock == 10
        assert repo.get_product(p.id) == p

    def test_ids_are_unique(self, repo):
        a = repo.add_product(product(sku="A-001"))
        b = repo.add_product(product(sku="B-001"))
        assert a.id != b.id

    def test_duplicate_sku_is_a_conflict(self, repo):
        repo.add_product(product())
        with pytest.raises(ConflictError):
            repo.add_product(product(name="Another mug"))

    def test_unknown_product(self, repo):
        with pytest.raises(NotFoundError):
            repo.get_product(999)

    def test_list_products_is_ordered_and_paginated(self, repo):
        ids = [repo.add_product(product(sku=f"SKU-{i:03d}")).id for i in range(5)]
        assert [p.id for p in repo.list_products()] == ids
        assert [p.id for p in repo.list_products(limit=2, offset=1)] == ids[1:3]
        assert repo.list_products(limit=10, offset=10) == []

    def test_place_order_computes_total_and_reduces_stock(self, repo):
        mug = repo.add_product(product(price_cents=1299, stock=10))
        tee = repo.add_product(product(sku="TEE-001", name="T-shirt", price_cents=2000, stock=3))
        o = repo.place_order(order((mug.id, 2), (tee.id, 1)))
        assert o.status == "created"
        assert o.total_cents == 2 * 1299 + 2000
        assert {(i.product_id, i.quantity, i.unit_price_cents) for i in o.items} == {
            (mug.id, 2, 1299),
            (tee.id, 1, 2000),
        }
        assert repo.get_product(mug.id).stock == 8
        assert repo.get_product(tee.id).stock == 2
        assert repo.get_order(o.id) == o

    def test_order_is_all_or_nothing(self, repo):
        mug = repo.add_product(product(stock=10))
        tee = repo.add_product(product(sku="TEE-001", stock=1))
        with pytest.raises(OutOfStockError):
            repo.place_order(order((mug.id, 2), (tee.id, 5)))
        assert repo.get_product(mug.id).stock == 10, "a failed order must not change any stock"

    def test_order_with_unknown_product(self, repo):
        mug = repo.add_product(product())
        with pytest.raises(NotFoundError):
            repo.place_order(order((mug.id, 1), (999, 1)))
        assert repo.get_product(mug.id).stock == 10

    def test_buying_the_last_item_is_allowed(self, repo):
        mug = repo.add_product(product(stock=1))
        repo.place_order(order((mug.id, 1)))
        assert repo.get_product(mug.id).stock == 0

    def test_price_is_frozen_at_order_time(self, repo):
        mug = repo.add_product(product(price_cents=1000))
        o = repo.place_order(order((mug.id, 1)))
        assert repo.get_order(o.id).items[0].unit_price_cents == 1000

    def test_cancel_restores_stock_once(self, repo):
        mug = repo.add_product(product(stock=5))
        o = repo.place_order(order((mug.id, 3)))
        cancelled = repo.cancel_order(o.id)
        assert cancelled.status == "cancelled"
        assert repo.get_product(mug.id).stock == 5
        with pytest.raises(ConflictError):
            repo.cancel_order(o.id)
        assert repo.get_product(mug.id).stock == 5, "cancelling twice must not add stock twice"

    def test_unknown_order(self, repo):
        with pytest.raises(NotFoundError):
            repo.get_order(999)
        with pytest.raises(NotFoundError):
            repo.cancel_order(999)

    def test_top_products_by_revenue(self, repo):
        mug = repo.add_product(product(sku="MUG-001", price_cents=1000, stock=50))
        tee = repo.add_product(product(sku="TEE-001", price_cents=2500, stock=50))
        cap = repo.add_product(product(sku="CAP-001", price_cents=500, stock=50))
        repo.place_order(order((mug.id, 3), (tee.id, 1)))  # mug 3000, tee 2500
        repo.place_order(order((cap.id, 2)))  # cap 1000
        cancelled = repo.place_order(order((tee.id, 10)))  # cancelled: must not count
        repo.cancel_order(cancelled.id)
        assert repo.top_products() == [("MUG-001", 3000), ("TEE-001", 2500), ("CAP-001", 1000)]
        assert repo.top_products(limit=1) == [("MUG-001", 3000)]

    def test_ping(self, repo):
        assert repo.ping() is None
