import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless RUN_TRACK17_INTEGRATION=1."""
    if os.environ.get("RUN_TRACK17_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="opt-in: set RUN_TRACK17_INTEGRATION=1 plus SEVENTEENTRACK_KEY and TRACK17_TEST_NUMBER")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
