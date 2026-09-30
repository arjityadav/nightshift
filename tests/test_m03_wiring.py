"""M3 · Wiring the API to PostgreSQL.   make check M=03"""

import yaml

from tinyshop.main import build_repository
from tinyshop.repository import InMemoryRepository


def test_without_database_url_use_memory():
    assert isinstance(build_repository({}), InMemoryRepository)
    assert isinstance(build_repository({"DATABASE_URL": "  "}), InMemoryRepository)


def test_compose_connects_api_to_db(root):
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    api = compose["services"]["api"]
    env = api.get("environment", {})
    url = env.get("DATABASE_URL", "") if isinstance(env, dict) else " ".join(env)
    assert "@db:5432/" in url, "inside compose, the database host is the service name `db`"
    dep = api.get("depends_on", {})
    assert isinstance(dep, dict) and dep.get("db", {}).get("condition") == "service_healthy", (
        "start the api only after the db healthcheck passes"
    )


def test_test_database_is_created(root):
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    mounts = " ".join(str(v) for v in compose["services"]["db"].get("volumes", []))
    assert "/docker-entrypoint-initdb.d" in mounts, "mount an init script that creates tinyshop_test"
    init = root / "deploy" / "postgres" / "init.sql"
    assert init.exists() and "tinyshop_test" in init.read_text()
