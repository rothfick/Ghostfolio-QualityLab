import os

import httpx
import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def api_client():
    base_url = os.getenv(
        "GHOSTFOLIO_BASE_URL",
        "http://localhost:3333",
    )

    with httpx.Client(
        base_url=base_url,
        timeout=10.0,
    ) as client:
        yield client


def test_application_is_alive(api_client):
    response = api_client.get("/api/v1/health/liveness")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "OK"


def test_application_dependencies_are_healthy(api_client):
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "OK"
