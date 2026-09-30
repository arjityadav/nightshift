"""Shared test setup. (Given: you don't need to change this file.)"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `import tinyshop` works without installing the project


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def pg_url() -> str:
    """URL of an EMPTY test database, recreated for every test. Tests using it are skipped
    unless TEST_DATABASE_URL is set (make test-db sets it)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set: start Postgres (make db) and run make test-db")
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    return url
