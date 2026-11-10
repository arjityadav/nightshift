"""Helpers for reading Prometheus metrics in tests. (Given: you don't need to change this file.)"""

from prometheus_client.parser import text_string_to_metric_families


def sample(text: str, name: str, **labels: str) -> float | None:
    """Value of the first sample called `name` whose labels include `labels`, or None.

    sample(text, "http_requests_total", route="/health", status="200") -> 3.0
    """
    for family in text_string_to_metric_families(text):
        for s in family.samples:
            if s.name == name and all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return None
