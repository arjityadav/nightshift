# M1 · HTTP APIs with FastAPI

**Time:** ~1 week · **Tests:** `make check M=01` · **You'll have:** TinyShop, a working shop API with products and orders, documented in Swagger UI, with an in-memory store.

TinyShop is the system Nightshift will operate. It's deliberately small, but it has the things real services have: validation, error codes, a data layer behind an interface, and health endpoints for Kubernetes.

---

## Concepts

### HTTP in five minutes

A client sends a **request**: a method, a path, headers and sometimes a body. The server returns a **response**: a status code, headers and usually a body. APIs almost always use JSON bodies.

```http
POST /orders HTTP/1.1
Content-Type: application/json

{"items": [{"product_id": 1, "quantity": 2}]}
```
```http
HTTP/1.1 201 Created
Content-Type: application/json

{"id": 7, "items": [...], "total_cents": 2598, "status": "created", "created_at": "..."}
```

| Method | Meaning | Safe? | Idempotent? |
|---|---|---|---|
| GET | read | yes | yes |
| POST | create / trigger an action | no | no |
| PUT | replace | no | yes |
| PATCH | partial update | no | not necessarily |
| DELETE | delete | no | yes |

*Idempotent* means doing it twice has the same effect as doing it once. It matters for retries: a client may safely retry a GET after a timeout, but retrying a POST can create two orders. (Real shops solve that with idempotency keys; a good interview topic.)

**Status codes you'll use:**

| Code | Meaning | TinyShop example |
|---|---|---|
| 200 OK | success | GET a product |
| 201 Created | something new was created | POST /products, POST /orders |
| 404 Not Found | the resource doesn't exist | GET /products/999 |
| 409 Conflict | valid request, but conflicts with current state | duplicate SKU, out of stock, cancelling twice |
| 422 Unprocessable Content | the body or parameters are invalid | negative price, empty order |
| 500 Internal Server Error | a bug on the server | never on purpose |
| 503 Service Unavailable | a dependency is down | `/ready` when the database is unreachable |

4xx means the client must change something; 5xx means the server has a problem. Alerting in M4 is built on this difference: a spike in 5xx pages someone, a spike in 404s usually doesn't.

**REST** means organising the API around *resources* (nouns: `/products`, `/orders/7`) and using methods for verbs. Actions that don't fit (cancel) become sub-resources: `POST /orders/7/cancel`.

### Pydantic: validation at the edge

Never trust input. Pydantic models declare what valid data looks like, and FastAPI rejects everything else with a 422 *before* your code runs:

```python
from pydantic import BaseModel, Field, field_validator

class BookIn(BaseModel):
    isbn: str = Field(pattern=r"^\d{13}$")             # regex the whole value must match
    title: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(gt=0)                    # greater than 0
    tags: list[str] = Field(default=[], max_length=5)  # on a list: at most 5 items

    @field_validator("tags")
    @classmethod
    def lower_case_tags(cls, tags: list[str]) -> list[str]:
        if any(t != t.lower() for t in tags):
            raise ValueError("tags must be lower case")   # becomes a 422
        return tags

class Book(BookIn):          # inheritance: everything from BookIn, plus an id
    id: int

book = BookIn(isbn="9780000000000", title="SRE", price_cents=3999)
book.model_dump()            # -> dict
Book(id=1, **book.model_dump())
book.model_copy(update={"price_cents": 2999})   # models are treated as immutable values: copy with changes
```

### FastAPI: a small example

This is *not* TinyShop; it shows every feature you need so you can write TinyShop yourself.

```python
from typing import Annotated
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

class BookNotFound(Exception):
    pass

class BookStore:                                   # a tiny "repository"
    def __init__(self):
        self.books: dict[int, Book] = {}
    def get(self, book_id: int) -> Book:
        if book_id not in self.books:
            raise BookNotFound(f"book {book_id} not found")
        return self.books[book_id]

def get_store(request: Request) -> BookStore:      # a dependency: FastAPI calls it per request
    return request.app.state.store

StoreDep = Annotated[BookStore, Depends(get_store)]

def create_app(store: BookStore) -> FastAPI:       # an "app factory"
    app = FastAPI(title="Books")
    app.state.store = store                        # objects the whole app shares

    @app.exception_handler(BookNotFound)           # domain error -> HTTP response, in ONE place
    async def not_found(request: Request, exc: BookNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/books/{book_id}")                   # path parameter, converted to int and validated
    def get_book(book_id: int, store: StoreDep) -> Book:     # return type = response model
        return store.get(book_id)

    @app.get("/books")                             # query parameters: /books?limit=10&offset=20
    def list_books(store: StoreDep,
                   limit: Annotated[int, Query(ge=1, le=100)] = 50,
                   offset: Annotated[int, Query(ge=0)] = 0) -> list[Book]:
        return list(store.books.values())[offset: offset + limit]

    @app.post("/books", status_code=201)           # a Pydantic parameter = the JSON body
    def add_book(data: BookIn, store: StoreDep) -> Book:
        book = Book(id=len(store.books) + 1, **data.model_dump())
        store.books[book.id] = book
        return book

    return app
```
- **The app factory** (`create_app(store)`) is what makes testing easy: tests pass a fresh store, production passes the real one.
- **Dependency injection** (`Depends`) means endpoints *ask* for what they need instead of creating it. In M3 you'll swap the in-memory store for PostgreSQL without touching a single endpoint.
- **Exception handlers** keep endpoints clean: the repository raises a domain error, one handler turns it into the right status code.
- **Parameters without defaults come first** in Python, so `store: StoreDep` goes before `limit=50`.
- FastAPI generates **OpenAPI** documentation from all of this: open `/docs` in a browser.

### The repository pattern

The API talks to storage only through an interface (a `Protocol`: "any object with these methods"). In M1 you implement it with Python dicts; in M3 with PostgreSQL. The same tests run against both, which is how you know the database version behaves correctly. This is called a **contract test**; see `tests/repo_contract.py`.

### Liveness vs readiness

Kubernetes (M6) asks every container two questions:
- **Liveness** (`/health`): is the process alive? If not, restart it. It must *not* check the database, or a database outage would make Kubernetes restart every app pod in a loop.
- **Readiness** (`/ready`): can it serve traffic right now? If not, stop sending requests to it until it recovers. This one *does* check dependencies.

---

## Step 1 · Dependencies

```bash
uv add fastapi "uvicorn[standard]"
```
FastAPI is the framework; uvicorn is the server that runs it.

## Step 2 · Errors (given)

Create `tinyshop/errors.py`:
```python
class ShopError(Exception):
    """Base class for domain errors."""


class NotFoundError(ShopError):
    pass


class OutOfStockError(ShopError):
    pass


class ConflictError(ShopError):
    pass
```

## Step 3 · Models: `tinyshop/models.py`

Write these Pydantic models (the tests in `tests/test_m01_models.py` show every rule):

| Model | Fields and rules |
|---|---|
| `ProductIn` | `sku: str` (3–20 chars of `A-Z`, `0-9`, `-`; use a regex pattern), `name: str` (1–100 chars), `price_cents: int` (> 0), `stock: int` (≥ 0) |
| `Product(ProductIn)` | adds `id: int` |
| `OrderItemIn` | `product_id: int` (> 0), `quantity: int` (1–100) |
| `OrderIn` | `items: list[OrderItemIn]`, 1 to 20 items, **no product twice** (a `field_validator`) |
| `OrderItem` | `product_id: int`, `quantity: int`, `unit_price_cents: int` (the price at the time of ordering) |
| `Order` | `id: int`, `items: list[OrderItem]`, `total_cents: int`, `status: Literal["created", "cancelled"]`, `created_at: datetime` |

`Literal["created", "cancelled"]` (from `typing`) means "only these two strings". Why does `OrderItem` store `unit_price_cents`? Because prices change. An order must keep the price the customer actually paid.

## Step 4 · The repository: `tinyshop/repository.py`

Start the file with the interface (given):
```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import Order, OrderIn, OrderItem, Product, ProductIn


class Repository(Protocol):
    def add_product(self, data: ProductIn) -> Product: ...
    def get_product(self, product_id: int) -> Product: ...
    def list_products(self, limit: int = 50, offset: int = 0) -> list[Product]: ...
    def place_order(self, data: OrderIn) -> Order: ...
    def get_order(self, order_id: int) -> Order: ...
    def cancel_order(self, order_id: int) -> Order: ...
    def top_products(self, limit: int = 5) -> list[tuple[str, int]]: ...
    def ping(self) -> None: ...
```

Then write `class InMemoryRepository` with the same methods. The behaviour (every point is tested in `tests/repo_contract.py`):

- **`add_product`** gives each product a new id (1, 2, 3, …). A SKU that already exists raises `ConflictError`.
- **`get_product`** / **`get_order`**: unknown id raises `NotFoundError`.
- **`list_products`** returns products ordered by id, skipping `offset` and returning at most `limit`.
- **`place_order`**:
  - unknown product → `NotFoundError`;
  - not enough stock for **any** item → `OutOfStockError`, and **no stock changes at all** (all or nothing);
  - otherwise reduce stock, record each item with the product's *current* price, compute `total_cents`, status `"created"`, `created_at = datetime.now(UTC)`.
- **`cancel_order`**: puts the stock back and sets status `"cancelled"`. Cancelling an already-cancelled order raises `ConflictError` (and must not add stock twice).
- **`top_products(limit)`**: `(sku, revenue_cents)` for products in **non-cancelled** orders, highest revenue first, then by SKU; at most `limit` rows.
- **`ping`**: does nothing and returns `None` (the in-memory store is always reachable).

<details>
<summary>Hints</summary>

- Store products and orders in two dicts keyed by id, plus two counters for the next ids.
- All or nothing: first loop over the items and *check* everything (existence and stock); only if every check passes, loop again and *apply* the changes. In M3, a database transaction gives you this for free.
- Pydantic models are values: to change stock, build a copy with `product.model_copy(update={"stock": new_stock})` and store the copy.
- `zip(products, data.items, strict=True)` walks two lists together.
- For `top_products`, add up revenue per product id in a dict, turn it into a list of tuples, and sort with `key=lambda r: (-r[1], r[0])`.
</details>

Run `make check M=01`: the repository tests (`TestInMemoryRepository`) should pass before you start the API.

## Step 5 · The API: `tinyshop/api.py`

Write `create_app(repo: Repository) -> FastAPI` with `title="TinyShop"`, `version=__version__` and these endpoints:

| Method and path | Success | Errors |
|---|---|---|
| `GET /health` | 200 `{"status": "ok", "version": "0.1.0"}` | – |
| `GET /ready` | 200 `{"status": "ready"}` after `repo.ping()` succeeds | 503 `{"status": "unavailable"}` if `ping()` raises anything |
| `POST /products` | 201 + the product | 422 invalid, 409 duplicate SKU |
| `GET /products?limit=50&offset=0` | 200 + list (`limit` 1–100, `offset` ≥ 0) | 422 invalid parameters |
| `GET /products/{product_id}` | 200 + product | 404 |
| `POST /orders` | 201 + order | 422 invalid, 404 unknown product, 409 out of stock |
| `GET /orders/{order_id}` | 200 + order | 404 |
| `POST /orders/{order_id}/cancel` | 200 + cancelled order | 404, 409 already cancelled |
| `GET /stats/top-products?limit=5` | 200 + `[{"sku": ..., "revenue_cents": ...}]` (`limit` 1–50) | 422 |

Error responses have the shape `{"detail": "<message>"}`. Map `NotFoundError` → 404 and both `OutOfStockError` and `ConflictError` → 409 with exception handlers. Use the Books example above as your pattern.

## Step 6 · Run it: `tinyshop/main.py`

```python
from tinyshop.api import create_app
from tinyshop.repository import InMemoryRepository

app = create_app(InMemoryRepository())
```
(In M3 this becomes "PostgreSQL if `DATABASE_URL` is set, otherwise in-memory".)

```bash
make run
```
Open **http://127.0.0.1:8000/docs**. This is Swagger UI, generated from your code. Try the whole flow by hand: create two products, place an order, try to order more than the stock (409), cancel the order, check the stock is back, look at `/stats/top-products`.

The same from the terminal with curl, which you'll use a lot in Docker and Kubernetes:
```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/products -H 'content-type: application/json' \
  -d '{"sku":"MUG-001","name":"Mug","price_cents":1299,"stock":10}'
curl -s -X POST localhost:8000/orders -H 'content-type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":2}]}'
curl -s -i localhost:8000/products/999        # -i shows the status line and headers
```

Change a file while `make run` is running: `--reload` restarts the server automatically.

---

## Definition of done

- [ ] `make check M=01` is green (models, repository contract, API).
- [ ] You placed and cancelled an order in Swagger UI and with curl.
- [ ] `make lint` is clean; committed and pushed (`git commit -m "M1: TinyShop API"`).

## Interview questions

1. **401 vs 403 vs 404 vs 409 vs 422?** 401: not authenticated. 403: authenticated but not allowed. 404: doesn't exist. 409: valid request that conflicts with the current state. 422: the request itself is invalid.
2. **Which HTTP methods are idempotent, and why does it matter?** GET, PUT, DELETE (and HEAD, OPTIONS). Clients and proxies retry on timeouts; retrying a non-idempotent POST can duplicate an order. Idempotency keys make POSTs safe to retry.
3. **Why an app factory and dependency injection?** Tests can build an app with fakes; production wires real dependencies; endpoints don't know which storage they use.
4. **Where should input validation happen?** At the boundary (request models), so invalid data never reaches business logic, plus database constraints as the last line of defence (M3).
5. **Liveness vs readiness?** Liveness: is the process alive (restart if not); never check dependencies there. Readiness: can it serve now (stop routing traffic if not); check dependencies.
6. **How do you keep an order "all or nothing"?** Validate everything before changing anything; in a database, wrap it in a transaction.

**Next:** [M2 · Docker](M02-docker.md)
