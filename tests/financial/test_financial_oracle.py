from decimal import Decimal

import pytest

from quality_lab.financial_oracle import Trade, calculate_ledger


D = Decimal


@pytest.mark.parametrize(
    ("trades", "expected_quantity", "expected_cash"),
    [
        pytest.param(
            [
                Trade("BUY", D("10"), D("100"), D("1")),
                Trade("SELL", D("4"), D("120"), D("2")),
            ],
            D("6"),
            D("-523"),
            id="partial-sale-with-fees",
        ),
        pytest.param(
            [
                Trade("BUY", D("10"), D("100")),
                Trade("SELL", D("10"), D("110")),
            ],
            D("0"),
            D("100"),
            id="fully-closed-position",
        ),
        pytest.param(
            [
                Trade("BUY", D("0.1"), D("10")),
                Trade("BUY", D("0.2"), D("10")),
            ],
            D("0.3"),
            D("-3"),
            id="fractional-quantities",
        ),
        pytest.param(
            [],
            D("0"),
            D("0"),
            id="empty-ledger",
        ),
    ],
)
def test_position_and_cash_flow(
    trades, expected_quantity, expected_cash
):
    result = calculate_ledger(trades)

    assert result.quantity == expected_quantity
    assert result.net_cash_flow == expected_cash


def test_sell_fee_reduces_proceeds():
    result = calculate_ledger([
        Trade("SELL", D("4"), D("120"), D("2"))
    ])

    assert result.net_cash_flow == D("478")
