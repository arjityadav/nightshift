class ShopError(Exception):
    """Base class for domain errors."""


class NotFoundError(ShopError):
    pass


class OutOfStockError(ShopError):
    pass


class ConflictError(ShopError):
    pass
