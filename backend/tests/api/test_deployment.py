"""
Ρυθμίσεις deployment που στηρίζουν τους κανόνες του backend: το backend δεν εκθέτει θύρα, εμπιστεύεται
X-Forwarded-For μόνο από το subnet του Nginx (όχι «*»), ένας worker, χωρίς access log του uvicorn (R6), και ο Nginx
ΑΝΤΙΚΑΘΙΣΤΑ το X-Forwarded-For με το $remote_addr.
"""
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
ROOT = Path(__file__).resolve().parents[3]


def _compose(name):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_backend_publishes_no_port():
    for name in ("docker-compose.yml", "docker-compose.prod.yml"):
        assert "ports" not in _compose(name)["services"]["backend"], name


def test_production_command_trusts_only_the_compose_subnet():
    prod = _compose("docker-compose.prod.yml")
    command = prod["services"]["backend"]["command"]
    for flag in ("--workers 1", "--proxy-headers", "--no-access-log"):
        assert flag in command
    trusted = re.search(r"--forwarded-allow-ips=\$\{FORWARDED_ALLOW_IPS:-([^}]+)\}", command)
    assert trusted, command
    assert "*" not in trusted.group(1)
    subnet = prod["networks"]["default"]["ipam"]["config"][0]["subnet"]
    assert trusted.group(1) == subnet
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(rf"^FORWARDED_ALLOW_IPS={re.escape(subnet)}$", env, re.M)


def test_dev_command_has_no_access_log():
    assert "--no-access-log" in _compose("docker-compose.yml")["services"]["backend"]["command"]


def test_nginx_replaces_forwarded_for():
    conf = (ROOT / "nginx" / "sites-available" / "pyramid.conf").read_text(encoding="utf-8")
    directives = re.findall(r"^\s*proxy_set_header\s+X-Forwarded-For\s+(\S+);", conf, re.M)
    assert directives and set(directives) == {"$remote_addr"}
    assert not re.search(r"^\s*[^#\n]*\$proxy_add_x_forwarded_for", conf, re.M)


# ---------- paths του backend (/api/v1) στον Nginx και στο Dockerfile ----------

def test_nginx_locations_use_the_api_prefix():
    from app.main import API_PREFIX
    conf = (ROOT / "nginx" / "sites-available" / "pyramid.conf").read_text(encoding="utf-8")
    locations = re.findall(r"^\s*location\s+(=\s+)?(\S+)\s*\{", conf, re.M)
    paths = [p for _, p in locations]
    assert f"{API_PREFIX}/meals/photo" in paths                          # Κανόνας 7: ειδικό buffer για τη φωτογραφία
    assert f"{API_PREFIX}/admin/" in paths                               # VPN μόνο: allow/deny
    admin = conf[conf.index(f"location {API_PREFIX}/admin/"):]
    admin = admin[:admin.index("}")]
    assert "allow" in admin and "deny  all" in admin
    assert not [p for p in paths if p.startswith("/api/") and p != "/api/" and not p.startswith(API_PREFIX)]


def test_nginx_access_log_has_no_query_string():
    conf = (ROOT / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    fmt = re.search(r"log_format\s+minimal\s+(.*?);", conf, re.S).group(1)
    assert "$uri" in fmt
    for var in ("$request ", '$request"', "$request_uri", "$args", "$query_string", "$request_body", "$http_authorization"):
        assert var not in fmt


def test_dockerfile_healthcheck_and_cmd():
    from app.main import API_PREFIX
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert f"localhost:8000{API_PREFIX}/health" in dockerfile
    cmd = re.search(r"^CMD \[(.*)\]$", dockerfile, re.M).group(1)
    assert '"--no-access-log"' in cmd and '"--workers", "1"' in cmd


def test_data_mounted_where_the_code_looks_for_it():
    """Στο container ο κώδικας είναι στο /app: lexicon.py -> parents[3]/data = /data, config.py -> parents[2]/data = /data."""
    container_lexicon = Path("/app/ai_pipeline/presentation/lexicon.py")
    container_config = Path("/app/app/config.py")
    assert container_lexicon.parents[3] / "data" == container_config.parents[2] / "data" == Path("/data")
    for name in ("docker-compose.yml", "docker-compose.prod.yml"):
        volumes = _compose(name)["services"]["backend"]["volumes"]
        assert "./data:/data:ro" in volumes, name
