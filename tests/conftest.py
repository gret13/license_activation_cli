from collections.abc import Callable
from functools import partial

import httpx
import pytest

from app.config import ClientConfig


@pytest.fixture
def license_key() -> str:
    return "Ds23-Da34-We21-E334"


@pytest.fixture
def device_data() -> dict[str, object]:
    return {
        "os_name": "WINDOWS",
        "cpu_arch": "AMD64",
        "cpu_cores": 8,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "motherboard_id": "BOARD-123",
    }


@pytest.fixture
def client_config() -> ClientConfig:
    return ClientConfig(host="127.0.0.1", port=55000)


@pytest.fixture
def mock_http(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], None]:
    original_client = httpx.Client

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        monkeypatch.setattr(
            httpx,
            "Client",
            partial(original_client, transport=httpx.MockTransport(handler)),
        )

    return install
