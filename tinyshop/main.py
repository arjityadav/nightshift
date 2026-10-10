import os
from collections.abc import Mapping

from tinyshop.api import create_app
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


app = create_app(build_repository(os.environ))
