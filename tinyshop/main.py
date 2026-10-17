import os
from collections.abc import Mapping

from tinyshop.api import create_app
from tinyshop.logs import configure_logging
from tinyshop.repository import InMemoryRepository, Repository


def build_repository(env: Mapping[str, str]) -> Repository:
    """DATABASE_URL set and not blank -> run migrate(url), return PostgresRepository(url).
    Otherwise -> InMemoryRepository(). (Import the Postgres modules inside the function, so
    the app still starts without psycopg installed.)"""
    url = env.get("DATABASE_URL", "").strip()
    if url:
        from tinyshop.db import migrate
        from tinyshop.pg_repository import PostgresRepository

        migrate(url)
        return PostgresRepository(url)
    else:
        return InMemoryRepository()


CHAOS_ENABLED = os.environ.get("CHAOS_ENABLED", "").lower() in ("1", "true", "yes")

configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
app = create_app(build_repository(os.environ), chaos_enabled=CHAOS_ENABLED)
