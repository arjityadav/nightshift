"""M3 · Schema migrations.   make test-db  (the SQL-file checks also run with make check M=03)"""

import re

import psycopg
import pytest

from tinyshop.db import migrate


def _sql_files(root):
    files = sorted((root / "migrations").glob("*.sql"))
    assert files, "create migrations/001_init.sql"
    return files


def test_migration_files_are_numbered(root):
    for f in _sql_files(root):
        assert re.match(r"^\d{3}_[a-z0-9_]+\.sql$", f.name), f"name like 001_init.sql, not {f.name}"


def test_schema_has_constraints(root):
    sql = "\n".join(f.read_text() for f in _sql_files(root)).lower()
    for table in ("products", "orders", "order_items"):
        assert f"create table {table}" in sql
    assert "unique" in sql, "sku must be UNIQUE"
    assert "check" in sql, "use CHECK constraints (price > 0, stock >= 0, ...)"
    assert "references" in sql, "order_items needs FOREIGN KEYs (REFERENCES)"
    assert "create index" in sql, "add at least one index"


@pytest.mark.postgres
def test_migrate_creates_tables_and_is_idempotent(pg_url):
    first = migrate(pg_url)
    assert first and first[0].startswith("001_")
    assert migrate(pg_url) == [], "running migrate() again must apply nothing"
    with psycopg.connect(pg_url) as conn:
        tables = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert {"products", "orders", "order_items", "schema_migrations"} <= tables
    assert versions == first


@pytest.mark.postgres
def test_database_enforces_the_rules(pg_url):
    migrate(pg_url)
    with psycopg.connect(pg_url) as conn:
        conn.execute("INSERT INTO products (sku, name, price_cents, stock) VALUES ('A-001', 'A', 100, 1)")
        conn.commit()
        for bad in [
            "INSERT INTO products (sku, name, price_cents, stock) VALUES ('A-001', 'dup', 100, 1)",
            "INSERT INTO products (sku, name, price_cents, stock) VALUES ('B-001', 'B', 0, 1)",
            "INSERT INTO products (sku, name, price_cents, stock) VALUES ('C-001', 'C', 100, -1)",
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)"
            " VALUES (999, 1, 1, 100)",
        ]:
            with pytest.raises(psycopg.errors.IntegrityError):
                conn.execute(bad)
            conn.rollback()


@pytest.mark.postgres
def test_failed_migration_is_rolled_back(pg_url, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE a (id int);")
    (tmp_path / "002_broken.sql").write_text("CREATE TABLE b (id int); SELECT * FROM does_not_exist;")
    with pytest.raises(psycopg.Error):
        migrate(pg_url, tmp_path)
    with psycopg.connect(pg_url) as conn:
        tables = {r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert "a" in tables and "b" not in tables, "a failed migration must leave no half-applied changes"
    assert versions == ["001_ok.sql"]
