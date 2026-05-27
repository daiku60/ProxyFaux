from rest_framework.test import APIClient


def test_health_endpoint_returns_ok() -> None:
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_root_returns_html_shell() -> None:
    response = APIClient().get("/", follow=False)

    assert response.status_code == 302
    assert response["Location"] == "/dashboard/"


def test_frontend_dashboard_returns_html_shell() -> None:
    response = APIClient().get("/dashboard/")

    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    assert '<script type="module" crossorigin src="/index.js"></script>' in response.content.decode()
