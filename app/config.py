import ipaddress
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from cryptography.x509 import Name

from app.licensing import license_hash


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class _Error:
    check_your_connection_to_the_server: str = "Ошибка: проверьте соединение с сервером"
    invalid_license_format: str = "Ошибка: неверный формат лицензии"
    invalid_license_checksum: str = "Ошибка: неверная контрольная сумма лицензии"
    input_interrupted: str = "Ввод прерван"
    invalid_server_response: str = "Ошибка сети. Проверьте соединение с сервером"
    failed_to_retrieve_device_information: str = (
        "Ошибка: не удалось получить информацию об устройстве"
    )
    unsupported_platform: str = "Ошибка: неподдерживаемая платформа"


@dataclass(frozen=True)
class _Info:
    config_file: str = "Файл конфигурации: config.toml"
    license_file: str = "Файл лицензии: license.txt"
    press_enter_to_exit: str = "Нажмите Enter для выхода..."


@dataclass(frozen=True)
class Message:
    error: _Error = _Error()
    info: _Info = _Info()


@dataclass(frozen=True)
class _Linux:
    board_path: Path = Path("/sys/class/dmi/id/board_serial")
    network_path: Path = Path("/sys/class/net")


@dataclass(frozen=True)
class _Window:
    network_path: Path = Path("/sys/class/net")


@dataclass(frozen=True)
class Paths:
    linux: _Linux = _Linux()
    window: _Window = _Window()


@dataclass(frozen=True)
class Fields:
    message: str = "message"
    status: str = "status"
    license_hash: str = "license_hash"
    payload: str = "payload"
    device: str = "device"
    type: str = "type"
    address: str = "address"
    wireless: str = "wireless"
    phy80211: str = "phy80211"
    windows: str = "windows"
    linux: str = "linux"
    MacAddress: str = "MacAddress"
    PhysicalMediaType: str = "PhysicalMediaType"
    NdisPhysicalMedium: str = "NdisPhysicalMedium"
    Name: str = "Name"
    InterfaceDescription: str = "InterfaceDescription"


@dataclass(frozen=True)
class ClientConfig:
    host: str
    port: int

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}/api/v1/licenses/activate"


def config_path() -> Path:
    base = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else (Path(__file__).resolve().parents[1])
    )
    return base / "config.toml"


def read_config(path: Path | None = None) -> ClientConfig:
    try:
        with (path or config_path()).open("rb") as handle:
            raw = tomllib.load(handle)
        if not isinstance(raw, dict) or set(raw) != {"api"}:
            raise ConfigError
        api = raw["api"]
        if not isinstance(api, dict) or set(api) != {"host", "port"}:
            raise ConfigError
        host = api["host"]
        port = api["port"]
        if (
            type(host) is not str
            or not host
            or host != host.strip()
            or type(port) is not int
        ):
            raise ConfigError
        if re.search(r"[/?#@\s]", host):
            raise ConfigError
        if ":" in host:
            ipaddress.IPv6Address(host)
        return ClientConfig(host=host, port=port)
    except (
        OSError,
        tomllib.TOMLDecodeError,
        ValueError,
        TypeError,
        ConfigError,
    ) as exc:
        raise ConfigError("Ошибка: файл конфигурации config.toml") from exc
