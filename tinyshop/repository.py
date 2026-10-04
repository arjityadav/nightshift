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


class InMemoryRepository:
    def __init__(self):
        self.products: dict[int, Product] = {}
        self.orders: dict[int, Order] = {}
        self.next_product_id: int = 1
        self.next_order_id: int = 1

    def add_product(self, data: ProductIn) -> Product:
        if any(p.sku == data.sku for p in self.products.values()):
            raise ConflictError(f"Product with SKU {data.sku} already exists")
        product = Product(id=self.next_product_id, **data.model_dump())
        self.products[self.next_product_id] = product
        self.next_product_id += 1
        return product

    def get_product(self, product_id: int) -> Product:
        product = self.products.get(product_id)
        if not product:
            raise NotFoundError(f"Product with id {product_id} not found")
        return product

    def list_products(self, limit: int = 50, offset: int = 0) -> list[Product]:
        return list(self.products.values())[offset : offset + limit]

    def place_order(self, data: OrderIn) -> Order:
        # check stock availibility
        for item in data.items:
            product = self.products.get(item.product_id)
            if not product:
                raise NotFoundError(f"Product with id {item.product_id} not found")
            if product.stock < item.quantity:
                raise OutOfStockError(f"Product with id {item.product_id} is out of stock")

        # create order
        order_items = []
        total_cents = 0
        for item in data.items:
            product = self.products.get(item.product_id)
            order_item = OrderItem(
                product_id=product.id, quantity=item.quantity, unit_price_cents=product.price_cents
            )
            order_items.append(order_item)
            total_cents += product.price_cents * item.quantity

        order = Order(
            id=self.next_order_id,
            items=order_items,
            total_cents=total_cents,
            status="created",
            created_at=datetime.now(UTC),
        )
        self.orders[self.next_order_id] = order
        self.next_order_id += 1

        # reduce stock
        for item in order.items:
            product = self.products.get(item.product_id)
            self.products[product.id] = product.model_copy(update={"stock": product.stock - item.quantity})

        return order

    def get_order(self, order_id: int) -> Order:
        order = self.orders.get(order_id)
        if not order:
            raise NotFoundError(f"Order with id {order_id} not found")
        return order

    def cancel_order(self, order_id: int) -> Order:
        order = self.orders.get(order_id)
        if not order:
            raise NotFoundError(f"Order with id {order_id} not found")
        if order.status == "cancelled":
            raise ConflictError(f"Order with id {order_id} is already cancelled")

        for item in order.items:
            product = self.products.get(item.product_id)
            self.products[product.id] = product.model_copy(update={"stock": product.stock + item.quantity})
        cancelled = order.model_copy(update={"status": "cancelled"})
        self.orders[order.id] = cancelled
        return cancelled

    def top_products(self, limit: int = 5) -> list[tuple[str, int]]:
        product_sales: dict[int, int] = {}
        for order in self.orders.values():
            if order.status == "cancelled":
                continue
            for item in order.items:
                item_price_total = item.unit_price_cents * item.quantity
                product_sales[item.product_id] = product_sales.get(item.product_id, 0) + item_price_total

        total_sales = [
            (self.products[product_id].sku, revenue) for product_id, revenue in product_sales.items()
        ]
        return sorted(total_sales, key=lambda x: (-x[1], x[0]))[:limit]

    def ping(self) -> None:
        # In-memory repository is always available
        pass
