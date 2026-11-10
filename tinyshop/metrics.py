from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        self.request = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "Histogram of HTTP request durations",
            ["method", "route"],
            registry=self.registry,
        )
        self.in_progress = Gauge(
            "http_requests_in_progress",
            "Number of HTTP requests in progress",
            [],
            registry=self.registry,
        )
        self.orders = Counter(
            "tinyshop_orders_total",
            "Total number of orders",
            ["result"],
            registry=self.registry,
        )
        self.chaos = Gauge(
            "tinyshop_chaos",
            "Chaos switch for simulating failures",
            ["switch"],
            registry=self.registry,
        )
