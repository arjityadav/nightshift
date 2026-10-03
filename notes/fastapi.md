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

## Datetimes
- `from datetime import UTC, datetime` (stdlib module and class share the name).
- **Naive** (no tzinfo) vs **aware** (`+00:00`). Comparing them raises `TypeError`. Always use aware UTC: `datetime.now(UTC)`.
- `datetime.utcnow()` is deprecated (3.12) and returns a naive datetime.

## Interview questions

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
