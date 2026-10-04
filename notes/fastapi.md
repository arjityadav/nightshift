# FastAPI & HTTP APIs

## Domain errors (`tinyshop/errors.py`)
```
Exception
 └── ShopError            base class for business errors
      ├── NotFoundError   → 404
      ├── OutOfStockError → 409
      └── ConflictError   → 409
```
- Repository raises domain errors and knows nothing about HTTP; the API maps them to status codes in **one place** (exception handlers). Same repository works from a CLI or a job.
- `except X:` catches X **and all its subclasses** (like `isinstance(exc, X)`). `except ShopError:` catches `OutOfStockError`, not `ValueError`.
- Real bugs (`KeyError`, `TypeError`) are not ShopErrors → they surface as 500s, which is what we want. Avoid bare `except Exception:`: it hides bugs.

## Pydantic models (`tinyshop/models.py`)
- Field syntax: `name: TYPE = DEFAULT_or_Field(rules)`. Type after the colon; no default = required.
- `Field(gt=0)`, `ge`, `le`, `min_length`/`max_length` (strings **and** lists), `pattern=` (Pydantic v2; `regex=` was removed).
- Regex: `^[A-Z0-9-]{3,20}$` → character class, quantifier `{min,max}`, anchors `^ $` so the whole value must match.
- `Literal["created", "cancelled"]` for a fixed set of values: a real type, shown as an enum in `/docs`. Better than a regex.
- `field_validator("items")` + `@classmethod` for custom rules; raise `ValueError` → 422. Duplicates: `len(ids) != len(set(ids))`.
- Nested models: `list[OrderItemIn]` turns plain dicts into validated models.
- Use real types (`datetime`, not `str` + regex); Pydantic converts to ISO 8601 in JSON.
- `default_factory=func` calls func **per instance** (like avoiding the mutable-default bug); `default=datetime.now()` would be evaluated once.
- Don't let a required field get a silent default (`stock`): missing data should be a 422, not a surprise 0.

## Repository (`tinyshop/repository.py`)
- `Repository` is a `Protocol` (an interface: "any object with these methods"). API depends on the Protocol, only `main.py` picks the implementation (in-memory now, Postgres in M3).
- **Contract tests** (`tests/repo_contract.py`) run the same tests against every implementation.
- **All or nothing:** check every item first, change state only if all checks pass (a DB transaction does this in M3).
- **Models are values:** read → `model_copy(update={...})` → store the copy. Mutating in place changes objects callers already hold; a DB always returns fresh copies, so in-memory must behave the same.
- `dict[...]` lookup when the key must exist → loud `KeyError`; `.get()` + `is None` when missing is a normal case.
- Sorting by several keys: `key=lambda r: (-r[1], r[0])` → tuples compare element by element; `-` reverses only that part.

## The API (`tinyshop/api.py`)
- **App factory** `create_app(repo)`: tests pass a fresh/fake repo, production passes the real one. No global state.
- **Dependency injection:** `RepoDep = Annotated[Repository, Depends(get_shop)]`; endpoints ask for `repo: RepoDep`. Overridable in tests (`app.dependency_overrides`).
- **Exception handlers** map domain errors → status codes once. No try/except in every endpoint ("whack-a-mole"); catching `Exception` there turned 404s into 409s.
- `status_code=201` on the decorator; **return the created object** (with id), not the input.
- **Return type = response model:** FastAPI validates the output (`ResponseValidationError` if it doesn't match), serialises datetimes, documents it in `/docs`. Don't `.model_dump()` yourself.
- `JSONResponse` only when one endpoint chooses between status codes (`/ready`, exception handlers). Plain `json` can't encode `datetime`.
- `Annotated[int, Query(ge=1, le=100)] = 50` for query params: validated, defaulted, documented. Parameters without defaults first.
- Path `/products/` ≠ `/products`; `405 Method Not Allowed` = path exists, method doesn't.
- The API layer shapes JSON: tuples from the repo → `TopProductStats` models.
- Pydantic error `loc` tells you where: `('response', 0, 'sku')` = response, item 0, field sku.

## HTTP
- 200 OK, 201 Created, 404 Not Found, 409 Conflict (valid but clashes with state), 422 invalid input, 500 server bug, 503 dependency down.
- 4xx = client must change something; 5xx = server problem (alerts in M4 are based on 5xx).
- **Idempotent:** doing it twice = doing it once. GET, PUT, DELETE yes; POST no (retry can create two orders → idempotency keys).
- **Liveness** `/health`: process alive? Never check the DB (a DB outage would restart every pod). **Readiness** `/ready`: can serve now? Checks dependencies → 503. `except Exception` is right here: any failure means "not ready".
- Kubernetes and load balancers read the **status code**, not the body.

## Datetimes
- `from datetime import UTC, datetime` (stdlib module and class share the name).
- **Naive** (no tzinfo) vs **aware** (`+00:00`). Comparing them raises `TypeError`. Always use aware UTC: `datetime.now(UTC)`.
- `datetime.utcnow()` is deprecated (3.12) and returns a naive datetime.

## Interview questions

**401 vs 403 vs 404 vs 409 vs 422?**
<details><summary>Answer</summary>
401 not authenticated; 403 authenticated but not allowed; 404 doesn't exist; 409 valid request that conflicts with current state (duplicate SKU, out of stock); 422 the request itself is invalid.
</details>

**Which HTTP methods are idempotent and why does it matter?**
<details><summary>Answer</summary>
GET, PUT, DELETE (and HEAD, OPTIONS). Clients and proxies retry on timeouts; retrying a non-idempotent POST can create a duplicate order. Idempotency keys make POSTs safe to retry.
</details>

**Why an app factory and dependency injection?**
<details><summary>Answer</summary>
Tests build the app with fakes (e.g. a broken repo for /ready), production wires real dependencies, and endpoints don't know which storage they use, so swapping in-memory for Postgres touches only main.py.
</details>

**Liveness vs readiness?**
<details><summary>Answer</summary>
Liveness: is the process alive, restart if not; never check dependencies. Readiness: can it serve now, stop routing traffic if not; checks dependencies and returns 503.
</details>

**Why exception handlers instead of try/except in each endpoint?**
<details><summary>Answer</summary>
One place maps each domain error to one status code; endpoints stay one-liners; new endpoints are covered automatically; catching broad exceptions per endpoint maps errors wrongly and hides bugs.
</details>

**Why store timestamps timezone-aware in UTC?**
<details><summary>Answer</summary>
One unambiguous reference time across servers and regions; aware datetimes can be compared and converted safely; naive ones are ambiguous and Python refuses to compare naive with aware. Convert to local time only for display.
</details>

**Why does `OrderItem` store `unit_price_cents` instead of looking up the product's price?**
<details><summary>Answer</summary>
Prices change and products can be deleted. An order is a historical record (snapshot) of what the customer actually paid; it must not change for history, invoices, refunds and revenue reports. A deliberate exception to "don't duplicate data". The repository copies `price_cents` into the order item when creating the order.
</details>

**Why use `default_factory` instead of `default` for a timestamp or list?**
<details><summary>Answer</summary>
`default` is evaluated once at class definition, so every instance shares the same value (same timestamp, same list). `default_factory` calls a function for each new instance.
</details>

**Why define your own exception hierarchy instead of raising `ValueError` everywhere?**
<details><summary>Answer</summary>
Domain errors have meaning (not found, out of stock, conflict), so each can map to the right HTTP status in one handler; a base class lets you catch all business errors without swallowing real bugs; the data layer stays independent of HTTP.
</details>

**Does `except ShopError:` catch an `OutOfStockError`? A `ValueError`?**
<details><summary>Answer</summary>
Yes for OutOfStockError (subclass, "is a" ShopError); no for ValueError (different branch). `except` matches the class and all subclasses.
</details>
