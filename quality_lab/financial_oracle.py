from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Literal


@dataclass(frozen=True)
class Trade:
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    unit_price: Decimal
    fee: Decimal = Decimal("0")


@dataclass(frozen=True)
class LedgerResult:
    quantity: Decimal
    net_cash_flow: Decimal


def calculate_ledger(trades: Iterable[Trade]) -> LedgerResult:
    quantity = Decimal("0")
    net_cash_flow = Decimal("0")

    for trade in trades:
        notional = trade.quantity * trade.unit_price

        if trade.side == "BUY":
            quantity += trade.quantity
            net_cash_flow -= notional + trade.fee
        elif trade.side == "SELL":
            quantity -= trade.quantity
            net_cash_flow += notional - trade.fee
        else:
            raise ValueError(f"Unsupported trade type: {trade.side}")

    return LedgerResult(
        quantity=quantity,
        net_cash_flow=net_cash_flow,
    )
