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

**Do foreign keys get an index automatically in PostgreSQL?**
<details><summary>Answer</summary>
No, only primary keys and UNIQUE constraints do. Unindexed foreign keys make joins and deletes on the parent table slow, so add the index yourself.
</details>
