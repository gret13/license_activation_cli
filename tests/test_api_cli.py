import json
from collections.abc import Callable

import httpx
import pytest

from app.api import ApiResult, ServerCommunicationError, activate
from app.cli import run
from app.config import ClientConfig, ConfigError, Message
from app.device import DeviceError
from app.licensing import license_hash


@pytest.mark.parametrize("status", [201, 400, 413, 429, 500, 503])
def test_api_response(
    status: int,
    license_key: str,
    device_data: dict[str, object],
    client_config: ClientConfig,
    mock_http: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert request.method == "POST"
        assert str(request.url) == client_config.url
        assert set(body) == {"license_hash", "payload"}
        assert body["license_hash"] == license_hash(license_key)
        assert isinstance(body["payload"], str)
        return httpx.Response(
            status,
            json={
                "status": "success" if status == 201 else "error",
                "code": "ACTIVATION_FAILED",
                "message": "result",
            },
        )

    mock_http(handler)
    result = activate(client_config, license_key, device_data)
    assert result == ApiResult(message="result", success=status == 201)
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("status", "data"),
    [
        (502, {"status": "error", "code": "X", "message": "x"}),
        (201, {"status": "error", "code": "X", "message": "x"}),
        (400, {"status": "success", "message": "x"}),
        (400, {"status": "error", "message": "x"}),
        (201, {"status": "success", "message": 17}),
        (201, ["unexpected"]),
    ],
)
def test_invalid_server_response(
    status: int,
    data: object,
    license_key: str,
    device_data: dict[str, object],
    client_config: ClientConfig,
    mock_http: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    mock_http(lambda request: httpx.Response(status, json=data))
    with pytest.raises(ServerCommunicationError) as exc_info:
        activate(client_config, license_key, device_data)
    assert str(exc_info.value) == Message.error.invalid_server_response


def test_invalid_server_json(
    license_key: str,
    device_data: dict[str, object],
    client_config: ClientConfig,
    mock_http: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    mock_http(lambda request: httpx.Response(201, content=b"not json"))
    with pytest.raises(ServerCommunicationError) as exc_info:
        activate(client_config, license_key, device_data)
    assert str(exc_info.value) == Message.error.invalid_server_response


@pytest.mark.parametrize("error", [httpx.ConnectError("offline"), httpx.ReadTimeout("timeout")])
def test_network_failure_does_not_retry(
    error: httpx.RequestError,
    license_key: str,
    device_data: dict[str, object],
    client_config: ClientConfig,
    mock_http: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise error

    mock_http(handler)
    with pytest.raises(ServerCommunicationError, match="Ошибка сети"):
        activate(client_config, license_key, device_data)
    assert attempts == 1


def test_cli_config_error_waits_for_enter(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing_config() -> None:
        raise ConfigError("Ошибка: файл конфигурации config.toml")

    monkeypatch.setattr("app.cli.read_config", missing_config)
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert run() == 1
    assert "Ошибка: файл конфигурации config.toml" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("key", "expected_message"),
    [
        ("not-a-license", "Ошибка: неверный формат лицензии"),
        ("Ds23-Da34-We21-E335", "Ошибка: неверная контрольная сумма лицензии"),
    ],
)
def test_cli_rejects_license_before_collecting_device(
    key: str,
    expected_message: str,
    client_config: ClientConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("app.cli.read_config", lambda: client_config)
    monkeypatch.setattr("app.cli.input_license", lambda: key)
    monkeypatch.setattr(
        "app.cli.collect_device",
        lambda: pytest.fail("Unexpected device collection"),
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert run() == 1
    assert expected_message in capsys.readouterr().out


@pytest.mark.parametrize("is_success", [True, False])
def test_cli_shows_server_result(
    is_success: bool,
    license_key: str,
    device_data: dict[str, object],
    client_config: ClientConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("app.cli.read_config", lambda: client_config)
    monkeypatch.setattr("app.cli.input_license", lambda: license_key)
    monkeypatch.setattr("app.cli.collect_device", lambda: device_data)
    monkeypatch.setattr(
        "app.cli.activate",
        lambda config, key, device: ApiResult("Ответ сервера", is_success),
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert run() == (0 if is_success else 1)
    assert "Ответ сервера" in capsys.readouterr().out


def test_cli_device_error(
    license_key: str,
    client_config: ClientConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def failing_device() -> None:
        raise DeviceError("Не удалось получить характеристики устройства")

    monkeypatch.setattr("app.cli.read_config", lambda: client_config)
    monkeypatch.setattr("app.cli.input_license", lambda: license_key)
    monkeypatch.setattr("app.cli.collect_device", failing_device)
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    assert run() == 1
    assert "Не удалось получить характеристики устройства" in capsys.readouterr().out
