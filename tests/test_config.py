from pathlib import Path

import pytest

from app.config import ConfigError, read_config


def test_valid_config(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[api]\nhost = "192.168.1.5"\nport = 55000\n', encoding="utf-8")
    assert read_config(file).url == "http://192.168.1.5:55000/api/v1/licenses/activate"


def test_ipv6_config(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[api]\nhost = "::1"\nport = 65535\n', encoding="utf-8")
    assert read_config(file).url == "http://[::1]:65535/api/v1/licenses/activate"


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"^Ошибка: файл конфигурации config.toml$"):
        read_config(tmp_path / "config.toml")


@pytest.mark.parametrize(
    "content",
    [
        "broken = [",
        "",
        '[api]\nhost = "127.0.0.1"',
        "[api]\nport = 55000",
        '[api]\nhost = "evil.com/path"\nport = 55000',
        '[api]\nhost = "127.0.0.1"\nport = "55000"',
        '[api]\nhost = " 127.0.0.1"\nport = 55000',
        '[api]\nhost = "127.0.0.1"\nport = 55000\nextra = true',
    ],
)
def test_invalid_config_has_single_error_message(tmp_path: Path, content: str) -> None:
    file = tmp_path / "config.toml"
    file.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=r"^Ошибка: файл конфигурации config.toml$"):
        read_config(file)


def test_custom_valid_port(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[api]\nhost = "127.0.0.1"\nport = 8000', encoding="utf-8")
    assert read_config(file).port == 8000


@pytest.mark.xfail(strict=True, reason="read_config currently accepts port outside 1..65535")
def test_out_of_range_port_rejected(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[api]\nhost = "127.0.0.1"\nport = 65536', encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config(file)
