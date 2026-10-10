from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def migrate(dsn: str, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every *.sql file in `migrations_dir` that hasn't been applied yet, in name order.

    - Create the table `schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ
      NOT NULL DEFAULT now())` if it doesn't exist.
    - Skip files whose name is already in schema_migrations.
    - Apply each new file AND record its name in ONE transaction, so a failing file leaves
      no half-applied changes and is not recorded. Files before it stay applied.
    - Return the names applied in this call, e.g. ["001_init.sql", "002_...sql"]; [] if none.
    """
    applied = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        applied_versions = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.name in applied_versions:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied
