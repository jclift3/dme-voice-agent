"""Shared fixtures. Isolates global state and forces the offline, deterministic
paths so unit/functional tests are fast and hermetic (no network, no keys)."""

import pytest
from fastapi.testclient import TestClient

from app import main, store


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    # No keys -> vendor matching uses the deterministic fallback and the callback
    # runs in mock mode. Clear the in-memory store so plan counts are predictable.
    for var in ("ANTHROPIC_API_KEY", "VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID"):
        monkeypatch.delenv(var, raising=False)
    store._PLANS.clear()
    main._CALL_BUFFERS.clear()
    yield
    store._PLANS.clear()
    main._CALL_BUFFERS.clear()


@pytest.fixture
def client():
    return TestClient(main.app)
