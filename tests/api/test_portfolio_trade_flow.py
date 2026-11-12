import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest

from quality_lab.financial_oracle import Trade, calculate_ledger


def test_buy_sell_position_matches_financial_oracle():
    token = os.getenv("GHOSTFOLIO_ACCESS_TOKEN")

    if not token:
        pytest.skip("GHOSTFOLIO_ACCESS_TOKEN is not set")

    base_url = os.getenv(
        "GHOSTFOLIO_BASE_URL",
        "http://localhost:3333",
    )

    if urlparse(base_url).hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail("Financial write tests require a local Ghostfolio")

    symbol = f"QLAB_{uuid4().hex[:12]}"
    trades = [
        Trade("BUY", Decimal("10"), Decimal("100"), Decimal("1")),
        Trade("SELL", Decimal("4"), Decimal("120"), Decimal("2")),
    ]
    expected = calculate_ledger(trades)
    created_ids = []

    with httpx.Client(base_url=base_url, timeout=20) as client:
        login = client.post(
            "/api/v1/auth/anonymous",
            json={"accessToken": token},
        )
        login.raise_for_status()
        client.headers.update({
            "Authorization": f"Bearer {login.json()['authToken']}"
        })

        existing = client.get(
            "/api/v1/activities",
            params={"symbol": symbol},
        )
        existing.raise_for_status()

        assert existing.json()["count"] == 0, (
            f"Test symbol {symbol} already has activities; "
            "refusing to modify an existing position"
        )

        try:
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

                if trade.side == "BUY":
                    profile = activity["assetProfile"]
                    assert profile["dataSource"] == "MANUAL"
                    assert profile["name"] == symbol
                    symbol = profile["symbol"]

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
                    actual_quantity = Decimal(
                        str(matching[0]["quantity"])
                    )

                if actual_quantity == expected.quantity:
                    break

                time.sleep(0.5)

            assert actual_quantity == expected.quantity, (
                f"Ghostfolio: {actual_quantity}, "
                f"financial oracle: {expected.quantity}"
            )

        finally:
            cleanup_errors = []

            for activity_id in reversed(created_ids):
                try:
                    response = client.delete(
                        f"/api/v1/activities/{activity_id}"
                    )
                    if not response.is_success:
                        cleanup_errors.append(
                            f"{activity_id}: HTTP {response.status_code}"
                        )
                except httpx.HTTPError as error:
                    cleanup_errors.append(
                        f"{activity_id}: {error}"
                    )

            if cleanup_errors:
                pytest.fail(
                    "Activity cleanup failed: "
                    + "; ".join(cleanup_errors)
                )
