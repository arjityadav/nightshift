import psycopg

from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import Order, OrderIn, Product, ProductIn


class PostgresRepository:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=psycopg.rows.dict_row)

    def add_product(self, product: ProductIn) -> Product:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                            INSERT INTO products (sku, name, price_cents, stock, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                            RETURNING id, sku, name, price_cents, stock
                            """,
                        (product.sku, product.name, product.price_cents, product.stock),
                    )
                    row = cur.fetchone()
                    return Product(**row)
        except psycopg.errors.UniqueViolation:
            raise ConflictError(f"Product with SKU {product.sku} already exists") from None

    def get_product(self, product_id: int) -> Product:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, sku, name, price_cents, stock
                    FROM products
                    WHERE id = %s
                    """,
                    (product_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise NotFoundError(f"Product with ID {product_id} not found")
                return Product(**row)

    def place_order(self, order: OrderIn) -> Order:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (product_id, quantity)
                    VALUES (%s, %s)
                    RETURNING id, status, total_cents, created_at
                    """,
                    (order.product_id, order.quantity),
                )
                row = cur.fetchone()
                if row is None:
                    raise OutOfStockError(f"Failed to place order for product ID {order.product_id}")
                return Order(**row)

    def get_order(self, order_id: int) -> Order:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, status, total_cents, created_at
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Order with ID {order_id} not found")
                return Order(**row)

    def cancel_order(self, order_id: int) -> Order:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET status = 'cancelled'
                    WHERE id = %s
                    RETURNING id, status, total_cents, created_at
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Order with ID {order_id} not found")
                return Order(**row)

    def top_products(self, limit: int) -> list[tuple[str, int]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.sku, SUM(p.price_cents * o.quantity) AS revenue
                    FROM products p
                    JOIN orders o ON p.id = o.product_id
                    WHERE o.status != 'cancelled'
                    GROUP BY p.sku
                    ORDER BY revenue DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return cur.fetchall()

    def ping(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    def list_products(self, limit: int = 50, offset: int = 0) -> list[Product]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, sku, name, price_cents, stock
                    FROM products
                    ORDER BY id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()
                return [Product(**row) for row in rows]
