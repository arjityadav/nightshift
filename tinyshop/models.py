from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProductIn(BaseModel):
    sku: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(gt=0)
    stock: int = Field(ge=0)


class Product(ProductIn):
    id: int = Field(gt=0)


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)

    @field_validator("items")
    @classmethod
    def check_unique_product_ids(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate product_id found in order items")
        return items


class OrderItem(OrderItemIn):
    unit_price_cents: int = Field(gt=0)


class Order(BaseModel):
    id: int = Field(gt=0)
    items: list[OrderItem] = Field(min_length=1, max_length=20)
    total_cents: int = Field(gt=0)
    status: Literal["created", "cancelled"]
    created_at: datetime
