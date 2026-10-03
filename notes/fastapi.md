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

## Interview questions

**Why define your own exception hierarchy instead of raising `ValueError` everywhere?**
<details><summary>Answer</summary>
Domain errors have meaning (not found, out of stock, conflict), so each can map to the right HTTP status in one handler; a base class lets you catch all business errors without swallowing real bugs; the data layer stays independent of HTTP.
</details>

**Does `except ShopError:` catch an `OutOfStockError`? A `ValueError`?**
<details><summary>Answer</summary>
Yes for OutOfStockError (subclass, "is a" ShopError); no for ValueError (different branch). `except` matches the class and all subclasses.
</details>
