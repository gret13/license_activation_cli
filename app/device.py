import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

from app.config import Fields, Message, Paths


class DeviceError(Exception):
    pass


BOARD_QUERY = (
    "(Get-CimInstance -ClassName Win32_BaseBoard -ErrorAction Stop).SerialNumber"
)

ADAPTER_QUERY = (
    "Get-NetAdapter -Physical -ErrorAction Stop | "
    "Select-Object Name, InterfaceDescription, MacAddress, PhysicalMediaType, NdisPhysicalMedium | "
    "ConvertTo-Json -Compress -Depth 3"
)

INVALID_BOARD_IDS = {
    "",
    "0",
    "NONE",
    "UNKNOWN",
    "DEFAULT STRING",
    "TO BE FILLED BY O.E.M.",
    "TO BE FILLED BY OEM",
    "NOT SPECIFIED",
    "SYSTEM SERIAL NUMBER",
    "123456789",
}

VIRTUAL_INDICATORS = (
    "VIRTUAL",
    "VMWARE",
    "VBOX",
    "VIRTUALBOX",
    "VPN",
    "TAP-",
    "WINTUN",
    "TUNNEL",
    "WIREGUARD",
    "HYPER-V",
    "BLUETOOTH",
    "LOOPBACK",
    "DOCKER",
    "NPCAP",
)
WI_FI_NAMES = ("WI-FI", "WIFI", "WIRELESS", "802.11")
ETHERNET_NAMES = ("ETHERNET", "802.3", "IEEE802_3", "802_3")
CONDENSED_PASS = {"000000000000", "FFFFFFFFFFFF"}
SYSTEM = platform.system().lower()


def _powershell(script: str) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        process = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=True,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DeviceError(Message.error.failed_to_retrieve_device_information) from exc

    return process.stdout.strip()


def _normal_text(text: str) -> str:
    return " ".join(text.split()).upper()


def _board_identifier(value: str) -> str | None:
    result = _normal_text(value)
    return result if result not in INVALID_BOARD_IDS else None


def normalize_mac(value: str) -> str | None:
    condensed = re.sub(r"[:.\-\s]", "", value).upper()

    if not re.fullmatch(r"[0-9A-F]{12}", condensed):
        return None

    if condensed in CONDENSED_PASS:
        return None

    return ":".join(condensed[i : i + 2] for i in range(0, 12, 2))


def _adapter_priority(adapter: dict[str, Any]) -> int | None:
    name = _normal_text(str(adapter.get(Fields.Name, "")))
    description = _normal_text(str(adapter.get(Fields.InterfaceDescription, "")))

    if any(blocked in name or blocked in description for blocked in VIRTUAL_INDICATORS):
        return None

    medium = _normal_text(str(adapter.get(Fields.PhysicalMediaType, "")))
    ndis = _normal_text(str(adapter.get(Fields.NdisPhysicalMedium, "")))
    combined = " ".join((name, description, medium, ndis))

    if any(item in combined for item in WI_FI_NAMES):
        return 1

    if any(item in combined for item in ETHERNET_NAMES):
        return 0

    return None


def choose_mac(adapters: object) -> str:
    items = adapters if isinstance(adapters, list) else [adapters]
    candidates: list[tuple[int, str]] = []

    for adapter in items:
        if not isinstance(adapter, dict):
            continue

        priority = _adapter_priority(adapter)
        mac = normalize_mac(str(adapter.get(Fields.MacAddress, "")))

        if priority is not None and mac is not None:
            candidates.append((priority, mac))

    if not candidates:
        raise DeviceError(Message.error.failed_to_retrieve_device_information)

    return min(candidates)[1]


def _collect_windows() -> tuple[str, str | None]:
    try:
        adapters = json.loads(_powershell(ADAPTER_QUERY))
        mac = choose_mac(adapters)
    except (ValueError, TypeError) as exc:
        raise DeviceError(Message.error.failed_to_retrieve_device_information) from exc

    try:
        board = _board_identifier(_powershell(BOARD_QUERY))
    except DeviceError:
        board = None

    return mac, board


def _linux_mac() -> str:
    network_path = Paths.linux.network_path
    candidates: list[tuple[int, str]] = []

    try:
        interfaces = list(network_path.iterdir())
    except OSError as exc:
        raise DeviceError(Message.error.failed_to_retrieve_device_information) from exc

    for interface in interfaces:
        if not (interface / Fields.device).exists():
            continue

        try:
            interface_type = (
                (interface / Fields.type).read_text(encoding="utf-8").strip()
            )

            if interface_type != "1":
                continue

            address = (interface / Fields.address).read_text(encoding="utf-8").strip()

        except (OSError, UnicodeError):
            continue

        mac = normalize_mac(address)

        if mac is None:
            continue

        is_wifi = (
            (interface / Fields.wireless).exists()
            or (interface / Fields.phy80211).exists()
            or interface.name.startswith("wl")
        )

        priority = 1 if is_wifi else 0
        candidates.append((priority, mac))

    if not candidates:
        raise DeviceError(Message.error.failed_to_retrieve_device_information)

    return min(candidates)[1]


def _linux_board_identifier() -> str | None:
    board_path = Paths.linux.board_path

    try:
        value = board_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    return _board_identifier(value)


def _collect_linux() -> tuple[str, str | None]:
    mac = _linux_mac()
    board = _linux_board_identifier()

    return mac, board


def collect_device() -> dict[str, object]:
    if SYSTEM.lower() not in {Fields.windows, Fields.linux}:
        raise DeviceError(Message.error.unsupported_platform)

    cores = os.cpu_count()

    if cores is None or cores <= 0 or cores > 32767:
        raise DeviceError(Message.error.failed_to_retrieve_device_information)

    if SYSTEM == Fields.windows:
        mac, board = _collect_windows()
    else:
        mac, board = _collect_linux()

    return {
        "os_name": _normal_text(SYSTEM),
        "cpu_arch": _normal_text(platform.machine()),
        "cpu_cores": cores,
        "mac_address": mac,
        "motherboard_id": board,
    }
