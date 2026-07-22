"""Test defaults that keep the local beginner workflow fast and predictable."""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("PYOS_RUN_QEMU", "").lower() in {"1", "true", "yes"}:
        return
    skip = pytest.mark.skip(reason="QEMU tests are opt-in; set PYOS_RUN_QEMU=1 to run them")
    for item in items:
        if "qemu" in item.keywords:
            item.add_marker(skip)
