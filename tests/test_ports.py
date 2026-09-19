"""Regression: browser must reach the API same-origin (no direct browser->backend).

Guards the loading-forever failure: next.config.ts must proxy /api/* to the
backend port, lib/api.ts must default to same-origin, and start.sh must serve
the backend on exactly that port.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_api_proxy_points_at_backend_port():
    next_config = (ROOT / "web" / "next.config.ts").read_text()
    assert "/api/:path*" in next_config
    assert "127.0.0.1:8000" in next_config


def test_frontend_defaults_to_same_origin():
    api_ts = (ROOT / "web" / "lib" / "api.ts").read_text()
    assert '?? ""' in api_ts


def test_start_script_serves_backend_on_proxy_port():
    start = (ROOT / "start.sh").read_text()
    assert "--port 8000" in start
    assert "NEXT_PUBLIC_API_URL=http" not in start  # must not bypass the proxy
