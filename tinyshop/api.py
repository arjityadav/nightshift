from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import OrderIn, ProductIn
from tinyshop.repository import InMemoryRepository


def get_shop(request: Request) -> InMemoryRepository:
    return request.app.state.store


def create_app(repo: InMemoryRepository) -> FastAPI:
    app = FastAPI(title="TinyShop", version="0.1.0")
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
        return JSONResponse(status_code=200, content={"status": "ok", "version": "0.1.0"})

    @app.get("/ready")
    def ready():
        """Ready check endpoint."""
        try:
            repo.ping()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not ready"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.post("/products", status_code=201)
    def create_product(product: ProductIn):
        """Create a new product."""
        product = repo.add_product(product)
        return product.model_dump()

    @app.get("/products")
    def get_products(
        limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0
    ):
        """Get a list of products."""
        return repo.list_products(limit, offset)

    @app.get("/products/{product_id}")
    def get_product(product_id: int):
        """Get a product by ID."""
        return repo.get_product(product_id).model_dump()

    @app.post("/orders", status_code=201)
    def create_order(order: OrderIn):
        """Create a new order."""
        order = repo.place_order(order)
        return order.model_dump()

    @app.get("/orders/{order_id}")
    def get_order(order_id: int):
        """Get an order by ID."""
        return repo.get_order(order_id)

    @app.post("/orders/{order_id}/cancel")
    def cancel_order(order_id: int):
        """Cancel an order."""
        return repo.cancel_order(order_id)

    @app.get("/stats/top-products")
    def get_top_products_stats(limit: Annotated[int, Query(ge=1, le=100)] = 5):
        """Get statistics for top products by revenue."""
        top_prod = repo.top_products(limit)
        return [{"sku": sku, "revenue_cents": revenue} for sku, revenue in top_prod]

    return app
