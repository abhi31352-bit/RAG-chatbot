"""Tests for health, readiness, and error-handling behaviour."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    # In production with FRONTEND_DIST set, / serves the SPA index.html.
    # Without it, / falls through to the SPA catch-all which returns 404
    # (no frontend/dist directory). Either way the route is handled.
    assert response.status_code in (200, 404)


async def test_health_check(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "app_name" in body
    assert "llm_model" in body


async def test_readiness_check(client):
    response = await client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert set(body["checks"].keys()) == {"database", "vector_store"}


async def test_openapi_schema_available(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()


async def test_rate_limiter_returns_429(client, monkeypatch):
    from app.config import settings
    from app.middleware import rate_limit

    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS_PER_MINUTE", 2)
    rate_limit.reset_rate_limits()

    assert (await client.get("/api/health")).status_code == 200
    assert (await client.get("/api/health")).status_code == 200
    third = await client.get("/api/health")

    assert third.status_code == 429
    body = third.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in third.headers

    rate_limit.reset_rate_limits()
