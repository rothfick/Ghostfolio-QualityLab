"""Enforce traceability between the risk catalog and pytest collection."""

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

COLUMNS = (
    "id", "area", "risk", "priority", "layer",
    "status", "scenario", "nodeid", "prerequisite",
)

PREFIXES = {
    "financial": "FIN",
    "portfolio": "PORT",
    "contracts": "CON",
    "security": "AUTH",
    "integrity": "DATA",
    "e2e": "E2E",
    "reliability": "REL",
    "health": "HLT",
}

LAYERS = {"unit", "integration", "e2e", "reliability"}
STATUSES = {"planned", "implemented", "blocked"}
PRIORITIES = {"P0", "P1", "P2"}


class TestCollector:
    def __init__(self):
        self.items = {}

    def pytest_collection_finish(self, session):
        self.items = {
            item.nodeid: {
                marker.name for marker in item.iter_markers()
            }
            for item in session.items
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "docs/test-catalog.csv",
    )
    args = parser.parse_args()

    with args.catalog.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if tuple(reader.fieldnames or ()) != COLUMNS:
            print("FAIL: Invalid catalog CSV header")
            return 1

        rows = list(reader)

    errors = []

    if len(rows) < 60:
        errors.append(
            f"Expected at least 60 catalog cases, found {len(rows)}"
        )

    ids = [row["id"] for row in rows]
    nodeids = [
        row["nodeid"]
        for row in rows
        if row["status"] == "implemented"
    ]

    for value, count in Counter(ids).items():
        if count > 1:
            errors.append(f"Duplicate test ID: {value}")

    for value, count in Counter(nodeids).items():
        if value != "-" and count > 1:
            errors.append(f"Duplicate pytest mapping: {value}")

    for number, row in enumerate(rows, start=2):
        case = row["id"]

        if not all(
            row.get(column) and row[column].strip()
            for column in COLUMNS
        ):
            errors.append(f"Row {number}: missing required field")
            continue

        if None in row:
            errors.append(f"Row {number}: extra CSV values")

        expected_prefix = PREFIXES.get(row["area"])

        if not expected_prefix:
            errors.append(f"{case}: unknown area")
        elif not re.fullmatch(
            rf"{expected_prefix}-\d{{3}}", case
        ):
            errors.append(f"{case}: invalid ID for area")

        if not re.fullmatch(r"R0[1-8]", row["risk"]):
            errors.append(f"{case}: invalid risk ID")

        if row["priority"] not in PRIORITIES:
            errors.append(f"{case}: invalid priority")

        if row["layer"] not in LAYERS:
            errors.append(f"{case}: invalid test layer")

        if row["status"] not in STATUSES:
            errors.append(f"{case}: invalid status")

        if row["status"] == "implemented":
            if row["nodeid"] == "-":
                errors.append(f"{case}: missing pytest node ID")
        elif row["nodeid"] != "-":
            errors.append(
                f"{case}: non-implemented case has pytest mapping"
            )

    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors))
        return 1

    collector = TestCollector()

    result = pytest.main(
        ["--collect-only", "-q", str(ROOT / "tests")],
        plugins=[collector],
    )

    if result != pytest.ExitCode.OK:
        print("FAIL: pytest collection did not succeed")
        return 1

    implemented = {
        row["nodeid"]: row
        for row in rows
        if row["status"] == "implemented"
    }

    collected = set(collector.items)
    mapped = set(implemented)

    for nodeid in sorted(collected - mapped):
        errors.append(f"Uncatalogued pytest test: {nodeid}")

    for nodeid in sorted(mapped - collected):
        errors.append(f"Missing pytest test: {nodeid}")

    for nodeid in sorted(collected & mapped):
        expected_layer = implemented[nodeid]["layer"]

        if expected_layer not in collector.items[nodeid]:
            errors.append(
                f"{nodeid}: expected marker {expected_layer}"
            )

    if errors:
        print("\n".join(f"FAIL: {error}" for error in errors))
        return 1

    print("\nTEST GOVERNANCE: PASSED")
    print(f"Catalog cases: {len(rows)}")
    print(f"Implemented:   {len(implemented)}")
    print(f"Planned:       {sum(r['status'] == 'planned' for r in rows)}")
    print(f"Blocked:       {sum(r['status'] == 'blocked' for r in rows)}")
    print("Traceability:  100% of collected tests mapped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
