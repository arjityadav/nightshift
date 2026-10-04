from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tinyshop import __version__
from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import Order, OrderIn, Product, ProductIn, TopProductStats
from tinyshop.repository import Repository


def get_shop(request: Request) -> Repository:
    return request.app.state.store


RepoDep = Annotated[Repository, Depends(get_shop)]


def create_app(repo: Repository) -> FastAPI:
    app = FastAPI(title="TinyShop", version=__version__)
    app.state.store = repo

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
