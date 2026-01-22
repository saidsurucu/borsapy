"""Pytest configuration for borsapy tests."""

import os

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires network connection)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is passed."""
    # Check for --run-integration flag or RUN_INTEGRATION env var
    run_integration = config.getoption("--run-integration", default=False)
    if not run_integration:
        run_integration = os.environ.get("RUN_INTEGRATION", "").lower() in (
            "1",
            "true",
            "yes",
        )

    if run_integration:
        # Don't skip integration tests
        return

    skip_integration = pytest.mark.skip(
        reason="Integration test requires --run-integration flag or RUN_INTEGRATION=1"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require network connection",
    )
