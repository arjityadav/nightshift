import logging
import re
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from tinyshop import __version__
from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.metrics import Metrics
from tinyshop.models import Order, OrderIn, Product, ProductIn, TopProductStats
from tinyshop.repository import Repository

access_log = logging.getLogger("tinyshop.access")

SAFE_ID = re.compile(r"[A-Za-z0-9-]{1,64}")


def get_shop(request: Request) -> Repository:
    return request.app.state.store


RepoDep = Annotated[Repository, Depends(get_shop)]


def create_app(repo: Repository) -> FastAPI:
    app = FastAPI(title="TinyShop", version=__version__)
    app.state.store = repo
    metrics = Metrics()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")

        if not request_id or not SAFE_ID.fullmatch(request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.perf_counter()

        response = await call_next(request)
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")

        if request.url.path != "/metrics":
            duration = time.perf_counter() - start
            access_log.log(
                logging.ERROR if response.status_code >= 500 else logging.INFO,
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "route": route_path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 1),
                },
            )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OutOfStockError)
    async def out_of_stock(request: Request, exc: OutOfStockError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        """Health check endpoint."""
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    def ready(repo: RepoDep):
        """Ready check endpoint."""
        try:
            repo.ping()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/metrics")
    def scrape() -> Response:
        """Metrics endpoint."""
        data = generate_latest(metrics.registry)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    @app.post("/products", status_code=201)
    def create_product(repo: RepoDep, product: ProductIn) -> Product:
        """Create a new product."""
        return repo.add_product(product)

    @app.get("/products")
    def get_products(
        repo: RepoDep,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[Product]:
        """Get a list of products."""
        return repo.list_products(limit, offset)

    @app.get("/products/{product_id}")
    def get_product(repo: RepoDep, product_id: int) -> Product:
        """Get a product by ID."""
        return repo.get_product(product_id)

    @app.post("/orders", status_code=201)
    def create_order(repo: RepoDep, order: OrderIn) -> Order:
        """Create a new order."""
        return repo.place_order(order)

    @app.get("/orders/{order_id}")
    def get_order(repo: RepoDep, order_id: int) -> Order:
        """Get an order by ID."""
        return repo.get_order(order_id)

    @app.post("/orders/{order_id}/cancel")
    def cancel_order(repo: RepoDep, order_id: int) -> Order:
        """Cancel an order."""
        return repo.cancel_order(order_id)

    @app.get("/stats/top-products")
    def get_top_products_stats(
        repo: RepoDep, limit: Annotated[int, Query(ge=1, le=50)] = 5
    ) -> list[TopProductStats]:
        """Get statistics for top products by revenue."""
        rows = repo.top_products(limit)
        return [TopProductStats(sku=sku, revenue_cents=revenue) for sku, revenue in rows]

    return app
