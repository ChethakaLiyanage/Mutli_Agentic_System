"""Shared backend-test configuration."""

from __future__ import annotations

import os


# Unit and regression tests must never consume a live LLM quota merely because
# a developer has configured Agent 4 locally.
os.environ["LLM_PROVIDER"] = "mock"
os.environ["PERSISTENCE_BACKEND"] = "memory"
