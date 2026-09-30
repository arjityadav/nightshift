# M3 · PostgreSQL

**Time:** ~1.5 weeks · **Tests:** `make check M=03` (no database needed) and `make test-db` (with PostgreSQL) · **You'll have:** TinyShop storing everything in PostgreSQL, with versioned migrations and orders that stay correct even when two customers buy the last item at the same moment.

SQL is one of the most asked-for skills in every engineering job, and PostgreSQL is the database you'll meet most often; with pgvector (M9) it's also your vector database. This module is also where your first real bug class appears: race conditions. Nightshift will later diagnose slow queries and connection problems in exactly this database.

---

## Concepts

### Tables, keys and constraints

A **table** has typed **columns** and holds **rows**. Every table gets a **primary key** (a unique id). A **foreign key** says "this column must match a row in another table", so an order item can't point to a product that doesn't exist.

TinyShop's schema:

```mermaid
erDiagram
  products ||--o{ order_items : "is ordered in"
  orders   ||--|{ order_items : contains
  products { bigint id PK
             text sku UK
             text name
             int price_cents
             int stock
             timestamptz created_at }
  orders   { bigint id PK
             text status
             int total_cents
             timestamptz created_at }
  order_items { bigint order_id PK,FK
                bigint product_id PK,FK
                int quantity
                int unit_price_cents }
```

`order_items` exists because an order has *many* products and a product appears in *many* orders (many-to-many). Storing a list of products inside `orders` would break the rules of **normalisation**: every fact is stored once, in one place.

**Constraints are your last line of defence.** Pydantic validates requests, but data also arrives through scripts, migrations and other services. `CHECK (stock >= 0)`, `UNIQUE`, `NOT NULL` and foreign keys make invalid data impossible, whichever code writes it.

Useful types: `BIGINT GENERATED ALWAYS AS IDENTITY` (auto-increment ids), `TEXT`, `INTEGER`, `TIMESTAMPTZ` (timestamp **with** time zone; always use it), `BOOLEAN`, `JSONB`.

### Indexes

Without an index, finding rows means reading the whole table (a *sequential scan*). An index (a B-tree by default) is like a book's index: it finds rows in O(log n). Primary keys and `UNIQUE` columns get an index automatically. **Foreign keys don't**, which is a classic cause of slow joins and deletes. Every index also slows writes a little and uses disk, so you add them for real queries, and check with `EXPLAIN ANALYZE`.

### Transactions (ACID)

A transaction groups statements so they happen **all or nothing**:
```sql
BEGIN;
UPDATE products SET stock = stock - 2 WHERE id = 1;
INSERT INTO orders (total_cents) VALUES (2598);
COMMIT;      -- or ROLLBACK; to undo everything since BEGIN
```
**A**tomic (all or nothing), **C**onsistent (constraints hold), **I**solated (concurrent transactions don't see each other's half-done work), **D**urable (after COMMIT it survives a crash).

### The race condition

Two customers, one mug left, both requests arrive at the same moment:

| Time | Request A | Request B |
|---|---|---|
| 1 | reads stock = 1 ✔ enough | |
| 2 | | reads stock = 1 ✔ enough |
| 3 | stock = 0, order created | |
| 4 | | stock = -1?! order created |

Both checks passed because both read *before* either wrote. This bug is called *check-then-act*, and it doesn't show up in normal tests, only under real concurrent load.

**The fix: lock the rows you're about to change.** `SELECT ... FOR UPDATE` locks the selected rows until your transaction ends; the second request **waits** at step 2, then reads the updated stock (0) and fails correctly. Two more rules:
- **Lock in a consistent order** (`ORDER BY id`). If A locks mug-then-shirt while B locks shirt-then-mug, each waits for the other forever: a **deadlock** (PostgreSQL detects it and kills one transaction).
- **Keep transactions short.** A lock held during a slow network call blocks everyone.

(Alternatives worth knowing for interviews: an atomic `UPDATE products SET stock = stock - 1 WHERE id = 1 AND stock >= 1` and check the affected row count; or *optimistic locking* with a version column. PostgreSQL's default isolation level is *Read Committed*; `SERIALIZABLE` also prevents this, at the cost of retries.)

### SQL injection and parameters

Never build SQL with f-strings from user input:
```python
conn.execute(f"SELECT * FROM products WHERE sku = '{sku}'")      # NEVER: sku = "x' OR '1'='1"
conn.execute("SELECT * FROM products WHERE sku = %s", (sku,))     # always: the driver sends data separately
```

### Migrations

The schema changes over time (new columns, new indexes), and every environment (your laptop, CI, staging, prod) must get the same changes, in the same order, exactly once. **Migrations** are numbered SQL files; a table `schema_migrations` records which ones have run. Rules: never edit a migration that has already run somewhere, add a new one instead; make changes backwards-compatible so old and new app versions can run side by side during a rolling deploy (M6). In companies you'll see tools like Alembic, Flyway or Liquibase; you'll write a tiny version yourself so you know what they do.

---

## Step 1 · SQL warm-up in psql

```bash
make db                                                   # just the database (M2)
docker compose exec db psql -U tinyshop -d tinyshop       # an interactive SQL prompt
```
Type these one by one and read the results (`\q` quits, `\dt` lists tables, `\d name` describes one):
```sql
CREATE TABLE fruit (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE, price_cents INTEGER CHECK (price_cents > 0));
INSERT INTO fruit (name, price_cents) VALUES ('apple', 50), ('pear', 80), ('kiwi', 30);
SELECT * FROM fruit;
SELECT name FROM fruit WHERE price_cents < 60 ORDER BY price_cents DESC;
SELECT count(*), sum(price_cents), avg(price_cents) FROM fruit;
UPDATE fruit SET price_cents = 60 WHERE name = 'apple' RETURNING *;
INSERT INTO fruit (name, price_cents) VALUES ('apple', 10);    -- UNIQUE violation
INSERT INTO fruit (name, price_cents) VALUES ('plum', -5);     -- CHECK violation
BEGIN; DELETE FROM fruit; SELECT count(*) FROM fruit; ROLLBACK; SELECT count(*) FROM fruit;
DROP TABLE fruit;
```

**Feel a row lock** with two terminals, both in psql:
```sql
-- setup, in terminal A:
CREATE TABLE mug (id int PRIMARY KEY, stock int);  INSERT INTO mug VALUES (1, 1);
-- A:
BEGIN; SELECT stock FROM mug WHERE id = 1 FOR UPDATE;
-- B:  (this HANGS: it's waiting for A's lock)
BEGIN; SELECT stock FROM mug WHERE id = 1 FOR UPDATE;
-- A:
UPDATE mug SET stock = stock - 1 WHERE id = 1; COMMIT;
-- B now continues and sees stock = 0. Then:
ROLLBACK; DROP TABLE mug;
```
Now repeat without `FOR UPDATE`: B doesn't wait and reads the stale value. That's the race.

## Step 2 · The first migration

```bash
mkdir migrations
```
Create `migrations/001_init.sql`. Here is the first table as an example; write `orders` and `order_items` yourself:
```sql
CREATE TABLE products (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    stock       INTEGER NOT NULL CHECK (stock >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
- **`orders`**: `id` (identity primary key), `status` (text, default `'created'`, only `'created'` or `'cancelled'` allowed: a `CHECK (status IN (...))`), `total_cents` (integer ≥ 0), `created_at` (timestamptz, default now).
- **`order_items`**: `order_id` (references `orders(id)`, `ON DELETE CASCADE`), `product_id` (references `products(id)`), `quantity` (1–100: `CHECK (quantity BETWEEN 1 AND 100)`), `unit_price_cents` (> 0); the primary key is the pair `(order_id, product_id)`.
- An index on `orders (created_at)`: reports ask "orders in the last hour" all the time.

Then `migrations/002_order_items_product_idx.sql`, because foreign keys aren't indexed automatically:
```sql
CREATE INDEX order_items_product_id_idx ON order_items (product_id);
```
Try your SQL in psql first; errors are much easier to read there.

## Step 3 · psycopg in five minutes

```bash
uv add "psycopg[binary]"
```
```python
import psycopg
from psycopg.rows import dict_row

url = "postgresql://tinyshop:tinyshop@localhost:5432/tinyshop"

with psycopg.connect(url, row_factory=dict_row) as conn:   # rows come back as dicts
    row = conn.execute("SELECT id, sku FROM products WHERE id = %s", (1,)).fetchone()   # dict or None
    rows = conn.execute("SELECT id FROM products WHERE id = ANY(%s)", ([1, 2, 3],)).fetchall()
    new = conn.execute("INSERT INTO products (sku, name, price_cents, stock) "
                       "VALUES (%(sku)s, %(name)s, %(price_cents)s, %(stock)s) RETURNING id",
                       {"sku": "A-001", "name": "A", "price_cents": 100, "stock": 1}).fetchone()
    with conn.transaction():           # a block that commits at the end, or rolls back on an exception
        ...
# leaving the `with connect(...)` block: COMMIT if no exception, ROLLBACK if there was one; then close
```
- `%s` placeholders take a tuple; `%(name)s` placeholders take a dict (handy with `model.model_dump()`).
- `RETURNING` gives you back the inserted or updated row, including generated ids and defaults.
- Database errors are exceptions: a UNIQUE violation is `psycopg.errors.UniqueViolation`; all constraint errors are subclasses of `psycopg.errors.IntegrityError`.
- **The autocommit trap:** a normal connection automatically opens a transaction at the first statement. A `with conn.transaction():` block inside that open transaction becomes a *savepoint*, not a real commit. So if you want each block to commit on its own (you do, in `migrate`), open the connection with `autocommit=True`; then every `conn.transaction()` block is a real BEGIN … COMMIT.
- Opening a connection per call is fine for now. In M6 you'll see why production apps use a **connection pool** (a classic incident: "too many connections").

## Step 4 · The migration runner: `tinyshop/db.py`

```python
from pathlib import Path

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
```
The tests check all four rules, including what happens when the second file is broken. `sorted(path.glob("*.sql"))` gives the files in order.

## Step 5 · The PostgreSQL repository: `tinyshop/pg_repository.py`

Write `class PostgresRepository` with `__init__(self, dsn: str)` and **exactly the same methods and behaviour** as `InMemoryRepository`. `tests/test_m03_postgres_repository.py` runs the same contract tests from M1 against it, plus two concurrency tests.

Method by method:

- **`add_product`**: `INSERT ... RETURNING id, sku, name, price_cents, stock`; build a `Product(**row)`. Catch `psycopg.errors.UniqueViolation` and raise `ConflictError` instead: the API must not know which database is behind it.
- **`get_product`**, **`list_products`**: `SELECT` with `WHERE id = %s`, or `ORDER BY id LIMIT %s OFFSET %s`.
- **`place_order`**: the important one. In **one transaction**:
  1. lock the products: `SELECT ... FROM products WHERE id = ANY(%s) ORDER BY id FOR UPDATE`;
  2. any id missing from the result → `NotFoundError`; any stock too low → `OutOfStockError` (raising inside the transaction rolls it back, so nothing changes);
  3. insert the order with the total and `RETURNING id, status, total_cents, created_at`;
  4. for each item: decrease stock and insert the `order_items` row with the current price;
  5. return the `Order`.
- **`get_order`**: the order row plus its items (`ORDER BY product_id`); `NotFoundError` if missing.
- **`cancel_order`**: in one transaction, lock the order row (`SELECT status FROM orders WHERE id = %s FOR UPDATE`); missing → `NotFoundError`; already cancelled → `ConflictError`; put the stock back and set the status. One statement can restock every product of the order:
  ```sql
  UPDATE products p SET stock = p.stock + oi.quantity
  FROM order_items oi WHERE oi.order_id = %s AND oi.product_id = p.id;
  ```
  Why lock the order row? Two simultaneous cancels would otherwise both see `created` and restock twice.
- **`top_products`**: one query with two `JOIN`s (`order_items` → `orders`, `order_items` → `products`), `WHERE o.status = 'created'`, `GROUP BY p.sku`, `SUM(oi.quantity * oi.unit_price_cents)`, `ORDER BY revenue DESC, p.sku`, `LIMIT %s`. `SUM` returns a `bigint`/`numeric`; add `::int` to get a plain int.
- **`ping`**: `SELECT 1`.

<details>
<summary>Hints</summary>

- A helper `def _connect(self): return psycopg.connect(self.dsn, row_factory=dict_row)` keeps every method short.
- `with self._connect() as conn, conn.transaction():` opens a connection and a transaction in one line.
- In `place_order`, build `wanted = {item.product_id: item.quantity for item in data.items}` and pass `list(wanted)` to `ANY(%s)`. Turn the locked rows into `{row["id"]: row}` to look them up.
- To load an order inside another method's transaction, write a private `_load_order(conn, order_id)` that takes the open connection, and use it from both `get_order` and `cancel_order`.
</details>

## Step 6 · Wire it up: `tinyshop/main.py`

```python
def build_repository(env: Mapping[str, str]) -> Repository:
    """DATABASE_URL set and not blank -> run migrate(url), return PostgresRepository(url).
    Otherwise -> InMemoryRepository(). (Import the Postgres modules inside the function, so
    the app still starts without psycopg installed.)"""

app = create_app(build_repository(os.environ))
```
Running migrations at start-up is fine for one instance. With several replicas in Kubernetes, you'll move them into a separate Job (M6); another interview topic.

Add migrations to the image. In the `Dockerfile` builder stage, after `COPY tinyshop ./tinyshop`:
```dockerfile
COPY migrations ./migrations
```

## Step 7 · Test against the real database

Add to the `Makefile`:
```makefile
test-db:            ## PostgreSQL tests against the tinyshop_test database (make db first)
	TEST_DATABASE_URL=postgresql://tinyshop:tinyshop@localhost:5432/tinyshop_test uv run pytest -q -m postgres
```
**These tests wipe the database they're given**, which is why they use `tinyshop_test` (created by your init script in M2) and never `tinyshop`. If `tinyshop_test` is missing because your volume existed before the init script, run `docker compose down -v` and `make db` again.

```bash
make check M=03    # file checks + wiring (no database needed); Postgres tests show as skipped
make db
make test-db       # contract tests, migrations and the race tests against real PostgreSQL
```

**Break it on purpose:** remove `FOR UPDATE` from `place_order` and run `make test-db` a few times. `test_two_customers_race_for_the_last_item` fails: you've reproduced a real concurrency bug. Put it back.

## Step 8 · Run the whole stack

```bash
make up
curl -s -X POST localhost:8000/products -H 'content-type: application/json' \
  -d '{"sku":"MUG-001","name":"Mug","price_cents":1299,"stock":10}'
curl -s -X POST localhost:8000/orders -H 'content-type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":2}]}'
docker compose restart api && sleep 5
curl -s localhost:8000/products/1          # still there, stock 8: it's in PostgreSQL now
curl -s localhost:8000/ready
docker compose stop db && sleep 2
curl -s -i localhost:8000/ready            # 503: readiness sees the database is gone
curl -s -i localhost:8000/health           # 200: liveness doesn't care (M1)
docker compose start db
```

Look inside:
```bash
docker compose exec db psql -U tinyshop -d tinyshop
```
```sql
\dt
SELECT * FROM schema_migrations;
EXPLAIN ANALYZE SELECT * FROM orders WHERE created_at > now() - interval '1 hour';
```
With only a few rows, PostgreSQL chooses a sequential scan: reading a tiny table is faster than using the index. Add 100,000 old orders, one per minute going back about 70 days, so "the last hour" is a small slice:
```sql
INSERT INTO orders (total_cents, created_at)
  SELECT 100, now() - g * interval '1 minute' FROM generate_series(1, 100000) AS g;
ANALYZE orders;                        -- refresh the planner's statistics
EXPLAIN ANALYZE SELECT * FROM orders WHERE created_at > now() - interval '1 hour';
-- Index Scan using orders_created_at_idx ... Execution Time: ~0.05 ms
DROP INDEX orders_created_at_idx;
EXPLAIN ANALYZE SELECT * FROM orders WHERE created_at > now() - interval '1 hour';
-- Seq Scan on orders ... Execution Time: ~5 ms (about 100 times slower, and it grows with the table)
CREATE INDEX orders_created_at_idx ON orders (created_at);
```
(If you had inserted the rows with the default `created_at = now()`, every row would be in the last hour and a sequential scan would be the right choice, even with the index. The planner picks by estimated cost, not by rule.) You'll use exactly this in M4 to create the "slow query" incident. Clean up with `docker compose down -v` when you're done experimenting.

---

## Definition of done

- [ ] `make check M=03` and `make test-db` are green, including both race tests.
- [ ] `make up`: orders survive `docker compose restart api`; `/ready` returns 503 while the database is stopped.
- [ ] You ran the two-terminal lock demo and the `EXPLAIN ANALYZE` experiment.
- [ ] All M0–M3 tests pass (`make test` plus `make test-db`); committed and pushed (`git commit -m "M3: PostgreSQL"`).

## Interview questions

1. **What does ACID mean?** Atomicity, consistency, isolation, durability: see the Concepts section.
2. **Two users buy the last item at the same time. What goes wrong and how do you prevent it?** Check-then-act race: both read stock 1, both sell. Lock the rows (`SELECT ... FOR UPDATE`) in a transaction, or use an atomic conditional `UPDATE ... WHERE stock >= n` and check the row count, or optimistic locking with a version column, or SERIALIZABLE with retries.
3. **What is a deadlock, and how do you avoid it?** Two transactions each wait for a lock the other holds. Always lock in the same order (e.g. by id), keep transactions short, and retry when the database aborts one.
4. **When do you add an index, and what does it cost?** For columns used in WHERE, JOIN and ORDER BY on large tables, confirmed with `EXPLAIN ANALYZE`. Costs: slower writes and extra storage. Foreign keys are not indexed automatically in PostgreSQL.
5. **How do you prevent SQL injection?** Parameterised queries; never string formatting with input. Plus least-privilege database users.
6. **How do you change a database schema without downtime?** Additive, backwards-compatible migrations (add a nullable column, deploy code that writes both, backfill, then switch reads, then drop the old column later), run once per environment, never edited after they've run.
7. **Why validate in both Pydantic and the database?** The API validates for good error messages; database constraints protect the data from every other writer and from bugs.
8. **Why do the same tests run against the in-memory and the PostgreSQL repository?** Contract tests prove both implementations behave the same, so the fast in-memory version is a trustworthy stand-in in unit tests.

**Next:** M4 · Observability and chaos: making TinyShop measurable, then breaking it on purpose. (Ask for the M4 lesson when you're here.)
