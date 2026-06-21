"""Shared fixtures. Isolates global state and forces the offline, deterministic
paths so unit and functional tests are fast and hermetic (no network, no keys)."""

import pytest
from fastapi.testclient import TestClient

from app import main, orchestrator


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    # No keys -> supplier outreach uses the deterministic path and the outbound call
    # runs in mock mode. Clear the in-memory store so plan counts are predictable.
    for var in ("ANTHROPIC_API_KEY", "VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID"):
        monkeypatch.delenv(var, raising=False)
    orchestrator._PLANS.clear()
    yield
    orchestrator._PLANS.clear()


@pytest.fixture
def client():
    return TestClient(main.app)
