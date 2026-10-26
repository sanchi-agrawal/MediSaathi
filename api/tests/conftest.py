"""Every API test is offline, even if the developer has a Gemini key."""
import socket
import pytest
from api.dependencies import reader


@pytest.fixture(autouse=True)
def forbid_live_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Live network / Gemini is forbidden in API tests")
    monkeypatch.setattr(reader.genai, "Client", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
