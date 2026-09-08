"""Test-only environment configuration loaded before application imports."""

import os

os.environ.setdefault(
    "SECRET_KEY",
    "test-only-secret-key-not-for-runtime-use-0001",
)
