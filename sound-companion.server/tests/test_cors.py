import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_preflight_allows_the_methods_the_client_uses(method):
    """The client calls these (rename is PATCH, delete is DELETE), so a browser without the Vite proxy needs them."""
    origin = settings.client_origins[0]
    response = TestClient(app).options(
        "/api/threads/x",
        headers={"Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": "content-type"},
    )
    assert response.status_code == 200
    assert method in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-origin"] == origin


def test_preflight_refuses_an_unknown_origin():
    response = TestClient(app).options(
        "/api/threads/x", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "DELETE"}
    )
    assert response.status_code == 400
