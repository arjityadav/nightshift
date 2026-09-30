"""M1 · Request/response models with Pydantic.   make check M=01"""

import pytest
from pydantic import ValidationError

from tinyshop.models import OrderIn, Product, ProductIn


def test_valid_product():
    p = ProductIn(sku="MUG-001", name="Mug", price_cents=1299, stock=10)
    assert p.price_cents == 1299
    assert Product(id=1, **p.model_dump()).id == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"sku": "mug-001"},  # lower case
        {"sku": "AB"},  # too short
        {"sku": "MUG 001"},  # space
        {"name": ""},
        {"name": "x" * 101},
        {"price_cents": 0},
        {"price_cents": -5},
        {"stock": -1},
    ],
)
def test_invalid_products(changes):
    data = {"sku": "MUG-001", "name": "Mug", "price_cents": 1299, "stock": 10} | changes
    with pytest.raises(ValidationError):
        ProductIn(**data)


def test_valid_order():
    o = OrderIn(items=[{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}])
    assert len(o.items) == 2


@pytest.mark.parametrize(
    "items",
    [
        [],  # empty order
        [{"product_id": 1, "quantity": 0}],
        [{"product_id": 1, "quantity": 101}],
        [{"product_id": 0, "quantity": 1}],
        [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}],  # duplicate product
        [{"product_id": i, "quantity": 1} for i in range(1, 22)],  # more than 20 lines
    ],
)
def test_invalid_orders(items):
    with pytest.raises(ValidationError):
        OrderIn(items=items)
