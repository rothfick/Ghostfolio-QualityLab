import os

import pytest


TEST_LEVELS = {"unit", "integration"}


def pytest_addoption(parser):
    parser.addoption(
        "--require-integration",
        action="store_true",
        help="Enforce integration prerequisites and disallow skipped tests",
    )


def pytest_sessionstart(session):
    if (
        session.config.getoption("--require-integration")
        and not os.getenv("GHOSTFOLIO_ACCESS_TOKEN")
    ):
        raise pytest.UsageError(
            "Integration gate requires GHOSTFOLIO_ACCESS_TOKEN"
        )


def pytest_collection_modifyitems(items):
    for item in items:
        levels = {
            marker.name
            for marker in item.iter_markers()
            if marker.name in TEST_LEVELS
        }

        if len(levels) != 1:
            raise pytest.UsageError(
                f"{item.nodeid}: expected exactly one test level "
                "(unit or integration)"
            )


def pytest_collection_finish(session):
    if not session.config.getoption("--require-integration"):
        return

    if not any(
        item.get_closest_marker("integration")
        for item in session.items
    ):
        raise pytest.UsageError(
            "Integration gate selected no integration tests"
        )


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--require-integration"):
        return

    reporter = session.config.pluginmanager.get_plugin(
        "terminalreporter"
    )

    if reporter and reporter.stats.get("skipped"):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if (
        config.getoption("--require-integration")
        and terminalreporter.stats.get("skipped")
    ):
        terminalreporter.write_sep(
            "=",
            "INTEGRATION GATE FAILED: skipped tests are not allowed",
        )
