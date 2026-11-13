import os
from urllib.parse import urlparse

import httpx
import pytest


@pytest.fixture
def authenticated_api():
    token = os.getenv("GHOSTFOLIO_ACCESS_TOKEN")

    if not token:
        pytest.skip("GHOSTFOLIO_ACCESS_TOKEN is not set")

    base_url = os.getenv(
        "GHOSTFOLIO_BASE_URL",
        "http://localhost:3333",
    )

    parsed_url = urlparse(base_url)

    if (
        parsed_url.scheme != "http"
        or parsed_url.hostname not in {"localhost", "127.0.0.1"}
    ):
        pytest.fail("Write tests require a local HTTP Ghostfolio instance")

    with httpx.Client(base_url=base_url, timeout=20) as client:
        login = client.post(
            "/api/v1/auth/anonymous",
            json={"accessToken": token},
        )
        login.raise_for_status()

        client.headers.update({
            "Authorization": f"Bearer {login.json()['authToken']}"
        })

        created_ids = []

        yield client, created_ids

        cleanup_errors = []

        # Delete only activities created by this test.
        for activity_id in reversed(created_ids):
            try:
                response = client.delete(
                    f"/api/v1/activities/{activity_id}"
                )

                if not response.is_success:
                    cleanup_errors.append(
                        f"DELETE {activity_id}: HTTP {response.status_code}"
                    )
            except httpx.HTTPError as error:
                cleanup_errors.append(
                    f"DELETE {activity_id}: {error}"
                )

        # Verify the deletion through an independent API read.
        for activity_id in created_ids:
            try:
                response = client.get(
                    f"/api/v1/activities/{activity_id}"
                )

                if response.status_code != 404:
                    cleanup_errors.append(
                        f"GET {activity_id}: expected 404, "
                        f"got {response.status_code}"
                    )
            except httpx.HTTPError as error:
                cleanup_errors.append(
                    f"GET {activity_id}: {error}"
                )

        if cleanup_errors:
            pytest.fail(
                "Test data cleanup verification failed:\n"
                + "\n".join(cleanup_errors)
            )

