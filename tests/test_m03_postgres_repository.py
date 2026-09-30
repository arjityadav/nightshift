"""M3 · PostgreSQL repository: the same contract as M1, plus concurrency.   make test-db"""

import threading

import pytest

from tests.repo_contract import RepositoryContract, order, product
from tinyshop.db import migrate
from tinyshop.errors import OutOfStockError


@pytest.mark.postgres
class TestPostgresRepository(RepositoryContract):
    @pytest.fixture
    def repo(self, pg_url):
        from tinyshop.pg_repository import PostgresRepository

        migrate(pg_url)
        return PostgresRepository(pg_url)


@pytest.mark.postgres
def test_two_customers_race_for_the_last_item(pg_url):
    """Two orders at the same moment for the last mug: exactly one may succeed."""
    from tinyshop.pg_repository import PostgresRepository

    migrate(pg_url)
    repo = PostgresRepository(pg_url)
    mug = repo.add_product(product(stock=1))
    results, barrier = [], threading.Barrier(2)

    def buy():
        barrier.wait()
        try:
            repo.place_order(order((mug.id, 1)))
            results.append("ok")
        except OutOfStockError:
            results.append("sold out")

    threads = [threading.Thread(target=buy) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "sold out"]
    assert repo.get_product(mug.id).stock == 0


@pytest.mark.postgres
def test_many_concurrent_orders_never_oversell(pg_url):
    from tinyshop.pg_repository import PostgresRepository

    migrate(pg_url)
    repo = PostgresRepository(pg_url)
    mug = repo.add_product(product(stock=5))
    ok = []

    def buy():
        try:
            repo.place_order(order((mug.id, 1)))
            ok.append(1)
        except OutOfStockError:
            pass

    threads = [threading.Thread(target=buy) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ok) == 5 and repo.get_product(mug.id).stock == 0
