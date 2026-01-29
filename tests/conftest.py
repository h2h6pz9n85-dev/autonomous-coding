"""
Pytest Configuration
====================

Shared fixtures and configuration for all tests.
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (may incur API costs, deselect with '-m \"not slow\"')"
    )
