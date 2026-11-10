"""M4 · The observability stack. These tests read your config files; the real test is opening
Grafana while TinyShop is under load and chaos (see "Definition of done").   make check M=04"""

import json
import re

import pytest
import yaml


@pytest.fixture
def compose(root):
    return yaml.safe_load((root / "compose.yaml").read_text())


def test_observability_services(compose):
    services = compose["services"]
    images = {
        "prometheus": "prom/prometheus",
        "grafana": "grafana/grafana",
        "loki": "grafana/loki",
        "alloy": "grafana/alloy",
    }
    for name, image in images.items():
        assert name in services, f"add a `{name}` service to compose.yaml"
        img = services[name]["image"]
        assert img.startswith(image + ":"), f"{name}: use the official {image} image"
        tag = img.split(":", 1)[1]
        assert re.match(r"v?\d+\.\d+", tag), f"{name}: pin a version, not {img}"


def test_chaos_is_enabled_only_in_the_local_stack(compose):
    env = compose["services"]["api"].get("environment", {})
    assert str(env.get("CHAOS_ENABLED", "")).lower() == "true", 'set CHAOS_ENABLED: "true" for the api'


def test_prometheus_scrapes_tinyshop(root):
    path = root / "deploy" / "prometheus" / "prometheus.yml"
    assert path.exists(), "create deploy/prometheus/prometheus.yml"
    cfg = yaml.safe_load(path.read_text())
    jobs = {job["job_name"]: job for job in cfg.get("scrape_configs", [])}
    assert "tinyshop" in jobs, "add a scrape job named `tinyshop`"
    targets = [t for sc in jobs["tinyshop"].get("static_configs", []) for t in sc["targets"]]
    assert "api:8000" in targets, "inside compose, Prometheus reaches the api by its service name"
    assert any("alerts" in f for f in cfg.get("rule_files", [])), "load your alert rules (rule_files)"


def test_alert_rules(root):
    path = root / "deploy" / "prometheus" / "alerts.yml"
    assert path.exists(), "create deploy/prometheus/alerts.yml"
    cfg = yaml.safe_load(path.read_text())
    rules = {r["alert"]: r for g in cfg["groups"] for r in g["rules"] if "alert" in r}
    for name in ("TinyShopDown", "TinyShopHighErrorRate", "TinyShopHighLatency"):
        assert name in rules, f"add the alert {name}"
        assert "for" in rules[name], f"{name}: add `for:` so a single bad scrape doesn't page anyone"
        assert rules[name].get("labels", {}).get("severity"), f"{name}: add labels.severity"
    assert "up{" in rules["TinyShopDown"]["expr"].replace(" ", "")
    errors = rules["TinyShopHighErrorRate"]["expr"]
    assert "rate(" in errors and "5.." in errors, "error ratio: rate of 5xx / rate of all requests"
    latency = rules["TinyShopHighLatency"]["expr"].replace(" ", "")
    assert "histogram_quantile(0.95" in latency, "latency: alert on p95 from the histogram"


def test_grafana_datasources(root):
    folder = root / "deploy" / "grafana" / "provisioning" / "datasources"
    files = sorted(folder.glob("*.y*ml"))
    assert files, "provision the data sources in deploy/grafana/provisioning/datasources/"
    sources = [d for f in files for d in yaml.safe_load(f.read_text())["datasources"]]
    by_type = {d["type"]: d for d in sources}
    assert by_type["prometheus"]["url"] == "http://prometheus:9090"
    assert by_type["loki"]["url"] == "http://loki:3100"


def _exprs(node) -> list[str]:
    if isinstance(node, dict):
        found = [v for k, v in node.items() if k == "expr" and isinstance(v, str)]
        return found + [e for v in node.values() for e in _exprs(v)]
    if isinstance(node, list):
        return [e for v in node for e in _exprs(v)]
    return []


def test_dashboard_is_provisioned(root):
    providers = root / "deploy" / "grafana" / "provisioning" / "dashboards"
    assert sorted(providers.glob("*.y*ml")), "add a dashboard provider in provisioning/dashboards/"
    dashboards = sorted((root / "deploy" / "grafana" / "dashboards").glob("*.json"))
    assert dashboards, "export your dashboard as JSON into deploy/grafana/dashboards/"
    exprs = [e for f in dashboards for e in _exprs(json.loads(f.read_text()))]
    joined = "\n".join(exprs)
    for needed in ("http_requests_total", "histogram_quantile", "tinyshop_chaos"):
        assert needed in joined, f"the dashboard needs a panel that queries {needed}"
    assert any(re.search(r"\|\s*(json|=|~)", e) for e in exprs), "add a logs panel with a LogQL query"


def test_alloy_ships_container_logs(root):
    path = root / "deploy" / "alloy" / "config.alloy"
    assert path.exists(), "create deploy/alloy/config.alloy"
    text = path.read_text()
    assert "loki.source.docker" in text and "http://loki:3100" in text


def test_locustfile(root):
    path = root / "loadtest" / "locustfile.py"
    assert path.exists(), "create loadtest/locustfile.py"
    text = path.read_text()
    for needed in ("HttpUser", "@task", "/products", "/orders", "catch_response"):
        assert needed in text, f"locustfile.py: missing {needed}"


def test_make_load_target(root):
    assert "\nload:" in "\n" + (root / "Makefile").read_text(), "add a `load` target to the Makefile"


def test_uvicorn_access_log_is_off(root):
    assert "--no-access-log" in (root / "Dockerfile").read_text(), (
        "TinyShop logs every request itself, as JSON: turn off uvicorn's plain-text access log"
    )
