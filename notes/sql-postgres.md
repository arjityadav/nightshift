# SQL & PostgreSQL

## Concepts
- **Table** = typed columns + rows. **Primary key** = unique id per row. **Foreign key** (`REFERENCES`) = value must exist in another table.
- **Normalisation:** every fact stored once. Many-to-many (orders ↔ products) needs a join table (`order_items`).
- **Constraints are the last line of defence:** `NOT NULL`, `UNIQUE`, `CHECK (...)`, foreign keys. The database rejects bad data from *any* writer (API, scripts, other services), not just the API that Pydantic protects.
- Errors name the constraint: `violates unique constraint "fruit_name_key"`, `violates check constraint "fruit_price_cents_check"`.
- Types: `BIGINT GENERATED ALWAYS AS IDENTITY` (auto id), `TEXT`, `INTEGER`, `TIMESTAMPTZ` (always with time zone), `BOOLEAN`, `JSONB`.
- **Indexes** (B-tree) find rows in O(log n) instead of a full scan. PKs and UNIQUE get one automatically; **foreign keys don't**. Indexes slow writes a little → add them for real queries, check with `EXPLAIN ANALYZE`.

## Transactions (ACID)
- **A**tomic (all or nothing), **C**onsistent (constraints hold), **I**solated (others don't see half-done work), **D**urable (survives a crash after COMMIT).
- Inside `BEGIN … ROLLBACK` you see your own changes (count 0 after DELETE); after ROLLBACK they're gone (count 3).

## The race condition (check-then-act)
- Two requests both read stock = 1 before either writes → both sell the last mug → stock -1.
- Doesn't show up in normal tests, only under concurrent load. (The in-memory repo never hit it: one process, one request at a time.)
- **Fix:** `SELECT ... FOR UPDATE` locks the rows until the transaction ends; the second request waits, then reads the fresh value.
- Lock rows in a consistent order (`ORDER BY id`) to avoid **deadlocks**; keep transactions short.
- Alternatives: atomic `UPDATE ... SET stock = stock - 1 WHERE id = 1 AND stock >= 1` + check row count; optimistic locking (version column); `SERIALIZABLE` isolation (with retries). Default isolation: Read Committed.

## SQL injection
- Never build SQL with f-strings from input (`sku = "x' OR '1'='1"`). Always parameters: `conn.execute("... WHERE sku = %s", (sku,))`; the driver sends data separately from the SQL.

## Migrations
- Numbered SQL files applied in order, exactly once, recorded in `schema_migrations`.
- Never edit a migration that already ran somewhere; add a new one. Keep changes backwards-compatible for rolling deploys.

## Schema design (my `001_init.sql`)
- `order_items` has a **composite primary key** `(order_id, product_id)` and no own id → the DB forbids the same product twice in one order.
- `ON DELETE CASCADE` only from owner → owned (order → its items). Never on `product_id`: deleting a product must not erase order history (default = block the delete).
- `DEFAULT 'created'` + `CHECK (status IN (...))` = SQL version of `Literal[...]`. The CHECK caught my `'placed'` typo.
- Let defaults do their job: insert only `total_cents`, the DB fills `status` and `created_at`.

## Migration runner (`tinyshop/db.py`)
- Connect with `autocommit=True`; each file + its `INSERT INTO schema_migrations` inside `with conn.transaction():` → they succeed or fail together; earlier files stay applied.
- Without autocommit, `conn.transaction()` is only a savepoint inside one big transaction.
- `CREATE TABLE IF NOT EXISTS` → safe to run every startup. `MIGRATIONS_DIR` found relative to `__file__`.

## psycopg 3 (not psycopg2!)
- `psycopg.connect(dsn, row_factory=dict_row)` → rows as dicts → `Product(**row)`.
- `%s` + tuple, `%(name)s` + dict; `RETURNING` gives back ids/defaults; `.fetchone()` (dict or None), `.fetchall()`.
- `with self._connect() as conn, conn.transaction():` = connection + one transaction; any exception rolls back.
- DB errors are **exceptions**, not `None` return values: catch `psycopg.errors.UniqueViolation` with try/except, `raise ConflictError(...) from None`. The API must not know which database is behind it.
- Try the insert and catch the violation instead of "check then insert" (that's a race).

## PostgresRepository
- `place_order`: one transaction; `SELECT ... WHERE id = ANY(%s) ORDER BY id FOR UPDATE`; check all → insert order → update stock + insert items; raising rolls back everything.
- `cancel_order`: lock the **order** row (`FOR UPDATE`) so two cancels can't restock twice; restock all items in one `UPDATE ... FROM order_items`.
- `_load_order(conn, ...)` reuses the open connection so it reads inside the caller's transaction.
- `top_products`: `JOIN` + `GROUP BY` + `SUM(...)::int`, revenue from `unit_price_cents` (price paid), `ORDER BY revenue DESC, sku`.
- Implementation signatures must match the Protocol exactly, defaults included.
- Contract tests: the same 14 tests pass for in-memory and Postgres; plus thread-based race tests. Removing `FOR UPDATE` makes the race test fail (sometimes: races are timing-dependent).

## Wiring (`main.py`)
- `build_repository(env)` receives the environment (testable with a dict): `DATABASE_URL` set and not blank → `migrate(url)` + `PostgresRepository`; else in-memory.
- Postgres imports inside the function so in-memory mode works without psycopg.
- Migrations at startup are fine for one instance; with replicas use a separate Job (M6).
- Green tests ≠ working app: an import bug in the Postgres branch was invisible to all tests → always run the real stack.

## psql
```sql
\dt            -- list tables
\d products    -- describe a table
\q             -- quit
```
`docker compose exec db psql -U tinyshop -d tinyshop`

## Interview questions

**What does ACID mean?**
<details><summary>Answer</summary>
Atomic: all statements in a transaction happen or none do. Consistent: constraints always hold. Isolated: concurrent transactions don't see each other's uncommitted work. Durable: committed data survives crashes.
</details>

**Two customers buy the last item at the same moment. What goes wrong and how do you prevent it?**
<details><summary>Answer</summary>
Check-then-act race: both read stock = 1 before either writes, both succeed, stock goes negative. Lock the rows with SELECT ... FOR UPDATE inside a transaction (in a consistent order to avoid deadlocks), or use an atomic conditional UPDATE and check the affected rows. A CHECK (stock >= 0) constraint is the final safety net.
</details>

**Why use database constraints if the API already validates input?**
<details><summary>Answer</summary>
Data also arrives through scripts, migrations, other services and bugs. Constraints make invalid data impossible regardless of who writes it; validation at the API is for good error messages, constraints are the last line of defence.
</details>

**How do you prevent SQL injection?**
<details><summary>Answer</summary>
Never concatenate user input into SQL; use parameterised queries so the driver sends values separately from the statement.
</details>

**What is a deadlock and how do you avoid it?**
<details><summary>Answer</summary>
Two transactions each wait for a lock the other holds. Lock rows in a consistent order (ORDER BY id), keep transactions short, and retry when the database aborts one.
</details>

**How do you change a schema without downtime?**
<details><summary>Answer</summary>
Additive, backwards-compatible migrations: add a nullable column, deploy code that writes both, backfill, switch reads, drop the old column later. Each migration runs once per environment and is never edited after it ran.
</details>

**Why do the same tests run against the in-memory and the PostgreSQL repository?**
<details><summary>Answer</summary>
Contract tests prove both implementations behave identically, so the fast in-memory version is a trustworthy stand-in for unit and API tests.
</details>

**Why should the repository translate database errors into domain errors?**
<details><summary>Answer</summary>
The API maps domain errors to status codes and must not depend on the storage technology; otherwise a UniqueViolation becomes a 500 and swapping databases changes the API.
</details>

**Do foreign keys get an index automatically in PostgreSQL?**
<details><summary>Answer</summary>
No, only primary keys and UNIQUE constraints do. Unindexed foreign keys make joins and deletes on the parent table slow, so add the index yourself.
</details>
