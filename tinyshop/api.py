from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tinyshop import __version__
from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import Order, OrderIn, Product, ProductIn
from tinyshop.repository import Repository


def get_shop(request: Request) -> Repository:
    return request.app.state.store


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
        return JSONResponse(status_code=200, content={"status": "ok", "version": __version__})

    @app.get("/ready")
    def ready():
        """Ready check endpoint."""
        try:
            repo.ping()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
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
    def get_product(product_id: int) -> Product:
        """Get a product by ID."""
        return repo.get_product(product_id).model_dump()

    @app.post("/orders", status_code=201)
    def create_order(order: OrderIn) -> Order:
        """Create a new order."""
        order = repo.place_order(order)
        return order.model_dump()

    @app.get("/orders/{order_id}")
    def get_order(order_id: int) -> Order:
        """Get an order by ID."""
        return repo.get_order(order_id)

    @app.post("/orders/{order_id}/cancel")
    def cancel_order(order_id: int):
        """Cancel an order."""
        return repo.cancel_order(order_id)

    @app.get("/stats/top-products")
    def get_top_products_stats(limit: Annotated[int, Query(ge=1, le=50)] = 5):
        """Get statistics for top products by revenue."""
        top_prod = repo.top_products(limit)
        return [{"sku": sku, "revenue_cents": revenue} for sku, revenue in top_prod]

    return app
