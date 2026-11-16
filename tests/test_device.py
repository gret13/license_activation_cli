from pathlib import Path
from types import SimpleNamespace

import pytest

from app import device
from app.device import DeviceError, _board_identifier, choose_mac, normalize_mac


@pytest.fixture
def physical_adapters() -> list[dict[str, str]]:
    return [
        {
            "Name": "Wi-Fi",
            "InterfaceDescription": "Intel Wireless",
            "MacAddress": "00-11-22-33-44-55",
        },
        {
            "Name": "Ethernet",
            "InterfaceDescription": "Intel Ethernet",
            "MacAddress": "AA-BB-CC-DD-EE-FF",
        },
        {
            "Name": "Ethernet 2",
            "InterfaceDescription": "Intel Ethernet",
            "MacAddress": "11-22-33-44-55-66",
        },
        {
            "Name": "VPN",
            "InterfaceDescription": "TAP-Windows Adapter",
            "MacAddress": "00-00-00-00-00-01",
        },
    ]


def test_choose_physical_ethernet_before_wifi(
    physical_adapters: list[dict[str, str]],
) -> None:
    assert choose_mac(physical_adapters) == "11:22:33:44:55:66"
    assert choose_mac(list(reversed(physical_adapters))) == "11:22:33:44:55:66"


def test_fallback_wifi() -> None:
    assert choose_mac(
        {
            "Name": "Wi-Fi",
            "InterfaceDescription": "Intel Wireless",
            "MacAddress": "001122334455",
        }
    ) == "00:11:22:33:44:55"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" To Be Filled By O.E.M. ", None),
        (" ", None),
        (" SN123 ", "SN123"),
        ("board-123", "BOARD-123"),
    ],
)
def test_board_identifier(raw: str, expected: str | None) -> None:
    assert _board_identifier(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("00.11.22.33.44.55", "00:11:22:33:44:55"),
        ("aa-bb-cc-dd-ee-ff", "AA:BB:CC:DD:EE:FF"),
        ("001122334455", "00:11:22:33:44:55"),
        ("00:11:22:33:44", None),
        ("00:00:00:00:00:00", None),
    ],
)
def test_mac_normalization(raw: str, expected: str | None) -> None:
    assert normalize_mac(raw) == expected


def test_rejects_virtual_adapters() -> None:
    with pytest.raises(DeviceError):
        choose_mac([{"Name": "VPN", "MacAddress": "AA-BB-CC-DD-EE-FF"}])


@pytest.mark.parametrize("board_value", ["To Be Filled By O.E.M.", "SN123"])
def test_collect_device_with_mocked_windows_hardware(
    board_value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device, "SYSTEM", "windows")
    monkeypatch.setattr(device.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(device.os, "cpu_count", lambda: 8)

    def fake_powershell(script: str) -> str:
        if "BaseBoard" in script:
            return board_value
        return (
            '[{"Name":"Ethernet","InterfaceDescription":"Intel Ethernet",'
            '"MacAddress":"AA-BB-CC-DD-EE-FF"}]'
        )

    monkeypatch.setattr(device, "_powershell", fake_powershell)
    assert device.collect_device() == {
        "os_name": "WINDOWS",
        "cpu_arch": "AMD64",
        "cpu_cores": 8,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "motherboard_id": None if board_value.startswith("To Be") else "SN123",
    }


def test_collect_device_rejects_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device, "SYSTEM", "darwin")
    with pytest.raises(DeviceError, match="неподдерживаемая платформа"):
        device.collect_device()


def test_collect_device_requires_positive_cpu_cores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(device, "SYSTEM", "windows")
    monkeypatch.setattr(device.os, "cpu_count", lambda: None)
    with pytest.raises(DeviceError, match="не удалось получить информацию об устройстве"):
        device.collect_device()


def test_linux_collect_uses_physical_ethernet_and_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = tmp_path / "net"
    ethernet = network / "enp1s0"
    wifi = network / "wlp2s0"
    virtual = network / "veth0"
    for interface, address in (
        (ethernet, "AA:BB:CC:DD:EE:FF"),
        (wifi, "00:11:22:33:44:55"),
        (virtual, "11:22:33:44:55:66"),
    ):
        interface.mkdir(parents=True)
        (interface / "type").write_text("1", encoding="utf-8")
        (interface / "address").write_text(address, encoding="utf-8")
    (ethernet / "device").mkdir()
    (wifi / "device").mkdir()
    board = tmp_path / "board_serial"
    board.write_text("SN123\n", encoding="utf-8")
    monkeypatch.setattr(
        device.Paths, "linux", SimpleNamespace(network_path=network, board_path=board)
    )
    monkeypatch.setattr(device, "SYSTEM", "linux")
    monkeypatch.setattr(device.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(device.platform, "machine", lambda: "x86_64")

    assert device.collect_device() == {
        "os_name": "LINUX",
        "cpu_arch": "X86_64",
        "cpu_cores": 8,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "motherboard_id": "SN123",
    }


def test_linux_missing_board_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = tmp_path / "net"
    ethernet = network / "enp1s0"
    ethernet.mkdir(parents=True)
    (ethernet / "device").mkdir()
    (ethernet / "type").write_text("1", encoding="utf-8")
    (ethernet / "address").write_text("AA:BB:CC:DD:EE:FF", encoding="utf-8")
    monkeypatch.setattr(
        device.Paths,
        "linux",
        SimpleNamespace(network_path=network, board_path=tmp_path / "missing"),
    )
    monkeypatch.setattr(device, "SYSTEM", "linux")
    monkeypatch.setattr(device.os, "cpu_count", lambda: 4)

    assert device.collect_device()["motherboard_id"] is None


def test_linux_no_physical_adapter_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = tmp_path / "net"
    virtual = network / "veth0"
    virtual.mkdir(parents=True)
    (virtual / "type").write_text("1", encoding="utf-8")
    (virtual / "address").write_text("AA:BB:CC:DD:EE:FF", encoding="utf-8")
    monkeypatch.setattr(
        device.Paths,
        "linux",
        SimpleNamespace(network_path=network, board_path=tmp_path / "missing"),
    )
    monkeypatch.setattr(device, "SYSTEM", "linux")
    monkeypatch.setattr(device.os, "cpu_count", lambda: 4)

    with pytest.raises(DeviceError, match="не удалось получить информацию об устройстве"):
        device.collect_device()
