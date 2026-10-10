import psycopg

from tinyshop.errors import ConflictError, NotFoundError, OutOfStockError
from tinyshop.models import Order, OrderIn, OrderItem, Product, ProductIn


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

    def place_order(self, data: OrderIn) -> Order:
        wanted = {item.product_id: item.quantity for item in data.items}  # {product_id: quantity}

        with self._connect() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, price_cents, stock
                    FROM products
                    WHERE id = ANY(%s)
                    ORDER BY id
                    FOR UPDATE
                    """,
                    (list(wanted),),
                )
                rows = cur.fetchall()
                products = {row["id"]: row for row in rows}

                for product_id, quantity in wanted.items():
                    if product_id not in products:
                        raise NotFoundError(f"Product with ID {product_id} not found")
                    if products[product_id]["stock"] < quantity:
                        raise OutOfStockError(f"Product with ID {product_id} is out of stock")
                cur.execute(
                    """
                    INSERT INTO orders (total_cents)
                    VALUES (%s)
                    RETURNING id, status, total_cents, created_at
                    """,
                    (sum(products[pid]["price_cents"] * qty for pid, qty in wanted.items()),),
                )
                order_row = cur.fetchone()

                for product_id, quantity in wanted.items():
                    cur.execute(
                        """
                        UPDATE products
                        SET stock = stock - %s
                        WHERE id = %s
                        """,
                        (quantity, product_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (order_row["id"], product_id, quantity, products[product_id]["price_cents"]),
                    )

                items = [
                    OrderItem(product_id=pid, quantity=qty, unit_price_cents=products[pid]["price_cents"])
                    for pid, qty in wanted.items()
                ]
                return Order(**order_row, items=items)

    def _load_order(self, conn: psycopg.Connection, order_id: int) -> Order:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, total_cents, created_at
                FROM orders
                WHERE id = %s
                """,
                (order_id,),
            )
            order_row = cur.fetchone()
            if order_row is None:
                raise NotFoundError(f"Order with ID {order_id} not found")

            cur.execute(
                """
                SELECT product_id, quantity, unit_price_cents
                FROM order_items
                WHERE order_id = %s
                ORDER BY product_id
                """,
                (order_id,),
            )
            item_rows = cur.fetchall()
            items = [OrderItem(**r) for r in item_rows]
            return Order(**order_row, items=items)

    def get_order(self, order_id: int) -> Order:
        with self._connect() as conn:
            return self._load_order(conn, order_id)

    def cancel_order(self, order_id: int) -> Order:
        with self._connect() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM orders
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                order_row = cur.fetchone()
                if order_row is None:
                    raise NotFoundError(f"Order with ID {order_id} not found")
                if order_row["status"] == "cancelled":
                    raise ConflictError(f"Order with ID {order_id} is already cancelled")

                cur.execute(
                    """
                    UPDATE products p
                    SET stock = p.stock + oi.quantity
                    FROM order_items oi
                    WHERE oi.order_id = %s AND oi.product_id = p.id
                    """,
                    (order_id,),
                )

                cur.execute(
                    """
                    UPDATE orders
                    SET status = 'cancelled'
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                return self._load_order(conn, order_id)

    def top_products(self, limit: int = 5) -> list[tuple[str, int]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.sku, SUM(oi.quantity * oi.unit_price_cents)::int AS revenue
                    FROM order_items oi
                    JOIN orders o   ON o.id = oi.order_id
                    JOIN products p ON p.id = oi.product_id
                    WHERE o.status = 'created'
                    GROUP BY p.sku
                    ORDER BY revenue DESC, p.sku
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [(r["sku"], r["revenue"]) for r in rows]

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
