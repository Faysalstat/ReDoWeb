"""Permission smoke tests for every /api/v1/admin/* route added in this
upgrade -- confirms require_admin's 403 gate actually covers each new
router, without needing a live Postgres (get_current_user is overridden
directly, bypassing the JWT/DB lookup it would otherwise do; the route
handlers themselves are never reached for a 403, so no DB connectivity is
required for this test). This does not test the "admin succeeds" path,
since that would require a live database for these read/write endpoints --
see docs/PROGRESS.md's precedent for admin_analytics_service.get_overview
having no unit test for the same reason (Project.submitted_ip is a
Postgres-only INET column the test suite's SQLite fixture can't compile).
"""

import types

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app

NON_ADMIN_USER = types.SimpleNamespace(id="11111111-1111-1111-1111-111111111111", is_admin=False, is_active=True)

ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/11111111-1111-1111-1111-111111111111"),
    ("POST", "/api/v1/admin/users/11111111-1111-1111-1111-111111111111/adjustments"),
    ("GET", "/api/v1/admin/costs/by-model"),
    ("GET", "/api/v1/admin/costs/by-user"),
    ("GET", "/api/v1/admin/costs/by-project"),
    ("GET", "/api/v1/admin/model-pricing"),
    ("PUT", "/api/v1/admin/model-pricing/openai/gpt-4o-mini"),
    ("GET", "/api/v1/admin/model-config/tiers"),
    ("PUT", "/api/v1/admin/model-config/tiers/pro"),
    ("PATCH", "/api/v1/admin/model-config/tiers/pro/active"),
    ("GET", "/api/v1/admin/model-config/vision-model"),
    ("PUT", "/api/v1/admin/model-config/vision-model"),
    ("GET", "/api/v1/admin/prompt-templates"),
    ("PATCH", "/api/v1/admin/prompt-templates/business_x_prompt.txt"),
    ("DELETE", "/api/v1/admin/prompt-templates/business_x_prompt.txt"),
    ("GET", "/api/v1/admin/earnings"),
    ("GET", "/api/v1/admin/overview"),
    ("GET", "/api/v1/admin/projects"),
]


@pytest.fixture
def client_as_non_admin():
    app.dependency_overrides[get_current_user] = lambda: NON_ADMIN_USER
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_rejects_non_admin(client_as_non_admin, method, path):
    response = client_as_non_admin.request(method, path, json={})
    assert response.status_code == 403


def test_admin_route_rejects_unauthenticated():
    client = TestClient(app)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401
