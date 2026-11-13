import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest

from quality_lab.financial_oracle import Trade, calculate_ledger


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


@pytest.mark.parametrize(
    "trades",
    [
        pytest.param(
            [
                Trade("BUY", Decimal("10"), Decimal("100"), Decimal("1")),
                Trade("SELL", Decimal("4"), Decimal("120"), Decimal("2")),
            ],
            id="partial-sale-with-fees",
        ),
        pytest.param(
            [
                Trade("BUY", Decimal("3"), Decimal("75"), Decimal("0.50")),
                Trade("SELL", Decimal("3"), Decimal("80"), Decimal("1.25")),
            ],
            id="full-position-closure",
        ),
        pytest.param(
            [
                Trade("BUY", Decimal("1.25"), Decimal("80"), Decimal("0.20")),
                Trade("SELL", Decimal("0.40"), Decimal("90"), Decimal("0.10")),
            ],
            id="fractional-quantities",
        ),
        pytest.param(
            [
                Trade("BUY", Decimal("5"), Decimal("100"), Decimal("1")),
                Trade("SELL", Decimal("2"), Decimal("125"), Decimal("1")),
                Trade("BUY", Decimal("3"), Decimal("90"), Decimal("0.50")),
                Trade("SELL", Decimal("1"), Decimal("110"), Decimal("0.50")),
            ],
            id="multi-leg-trading",
        ),
    ],
)
def test_trade_scenarios_match_financial_oracle(authenticated_api, trades):
    client, created_ids = authenticated_api

    symbol = f"QLAB_{uuid4().hex[:12]}"
    expected = calculate_ledger(trades)

    existing = client.get(
        "/api/v1/activities",
        params={"symbol": symbol},
    )
    existing.raise_for_status()

    assert existing.json()["count"] == 0, (
        f"Test symbol {symbol} already exists"
    )

    for index, trade in enumerate(trades):
        date = datetime.now(timezone.utc) - timedelta(
            days=7 - index
        )

        payload = {
            "currency": "USD",
            "dataSource": "MANUAL",
            "date": date.isoformat().replace("+00:00", "Z"),
            "fee": float(trade.fee),
            "quantity": float(trade.quantity),
            "symbol": symbol,
            "type": trade.side,
            "unitPrice": float(trade.unit_price),
        }

        response = client.post(
            "/api/v1/activities",
            json=payload,
        )
        assert response.is_success, response.text

        activity = response.json()
        created_ids.append(activity["id"])

        profile = activity["assetProfile"]
        assert profile["dataSource"] == "MANUAL"

        if index == 0:
            assert trade.side == "BUY"
            assert profile["name"] == symbol
            symbol = profile["symbol"]
        else:
            assert profile["symbol"] == symbol

    activities_response = client.get(
        "/api/v1/activities",
        params={"symbol": symbol},
    )
    activities_response.raise_for_status()

    activities = activities_response.json()["activities"]

    assert {item["id"] for item in activities} == set(created_ids)

    actual_cash_flow = Decimal("0")

    for activity, trade in zip(
        sorted(activities, key=lambda item: item["date"]),
        trades,
        strict=True,
    ):
        assert activity["type"] == trade.side
        assert Decimal(str(activity["quantity"])) == trade.quantity
        assert Decimal(str(activity["unitPrice"])) == trade.unit_price
        assert Decimal(str(activity["fee"])) == trade.fee

        notional = Decimal(str(activity["value"]))
        assert notional == trade.quantity * trade.unit_price

        if activity["type"] == "BUY":
            actual_cash_flow -= notional + trade.fee
        else:
            actual_cash_flow += notional - trade.fee

    assert actual_cash_flow == expected.net_cash_flow

    actual_quantity = None

    for _ in range(10):
        response = client.get(
            "/api/v1/portfolio/holdings",
            params={"symbol": symbol},
        )
        response.raise_for_status()

        matching = [
            item for item in response.json()["holdings"]
            if item["assetProfile"]["symbol"] == symbol
            and item["assetProfile"]["dataSource"] == "MANUAL"
        ]

        if matching:
            actual_quantity = Decimal(str(matching[0]["quantity"]))

        if actual_quantity == expected.quantity:
            break

        time.sleep(0.5)

    assert actual_quantity == expected.quantity, (
        f"Ghostfolio: {actual_quantity}, "
        f"financial oracle: {expected.quantity}"
    )
