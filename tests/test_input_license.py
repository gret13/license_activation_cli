import sys
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace

import pytest

from app import input_license as input_module
from app.input_license import format_license, read_windows_input


def key_reader(keys: str) -> Iterator[str]:
    return iter(keys)


def test_live_format_keeps_mixed_case(capsys: pytest.CaptureFixture[str]) -> None:
    keys = key_reader("ds23da34we21e33f\r")
    actual = read_windows_input(lambda: next(keys))
    assert actual == "ds23-da34-we21-e33f"
    printed = capsys.readouterr().out
    assert "ds23-da34-we21-e33f" in printed
    assert "ds23-" in printed


def test_pasted_hyphens_and_backspace() -> None:
    keys = key_reader("Ds23-Da34-We21-E33X\b4\r")
    assert read_windows_input(lambda: next(keys)) == "Ds23-Da34-We21-E334"


def test_four_group_limit_and_backspace(capsys: pytest.CaptureFixture[str]) -> None:
    keys = key_reader("AB12CD34EF56GH78Q\r")
    assert read_windows_input(lambda: next(keys)) == "AB12-CD34-EF56-GH78"
    assert format_license("AB12", trailing_separator=True) == "AB12-"
    assert format_license("AB12") == "AB12"
    assert capsys.readouterr().out


def test_special_keys_do_not_change_input() -> None:
    keys = key_reader("AB12\xe0H\x00Pcd34\r")
    assert read_windows_input(lambda: next(keys)) == "AB12-cd34"


def test_ctrl_c_interrupts_input() -> None:
    keys = key_reader("AB12\x03")
    with pytest.raises(KeyboardInterrupt):
        read_windows_input(lambda: next(keys))


def test_linux_reads_character_and_backspace(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = iter([b"A", b"\x7f", b"B"])
    monkeypatch.setattr(input_module.os, "read", lambda fd, length: next(keys))
    assert input_module._read_linux_key(5) == "A"
    assert input_module._read_linux_key(5) == "\x7f"
    assert input_module._read_linux_key(5) == "B"


def test_linux_input_restores_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    termios = ModuleType("termios")
    tty = ModuleType("tty")
    setattr(termios, "tcgetattr", lambda fd: [1, 2, 3])
    setattr(termios, "tcsetattr", lambda fd, mode, settings: calls.append((fd, mode, settings)))
    setattr(termios, "TCSADRAIN", 1)
    setattr(tty, "setcbreak", lambda fd: calls.append(("cbreak", fd)))
    monkeypatch.setitem(sys.modules, "termios", termios)
    monkeypatch.setitem(sys.modules, "tty", tty)
    monkeypatch.setattr(input_module.sys, "stdin", SimpleNamespace(fileno=lambda: 7))
    keys = iter("AB12\r")
    monkeypatch.setattr(input_module, "_read_linux_key", lambda fd: next(keys))
    assert input_module.read_linux_input() == "AB12"
    assert calls == [("cbreak", 7), (7, 1, [1, 2, 3])]


def test_linux_input_restores_terminal_after_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    termios = ModuleType("termios")
    tty = ModuleType("tty")
    setattr(termios, "tcgetattr", lambda fd: [1, 2, 3])
    setattr(termios, "tcsetattr", lambda fd, mode, settings: calls.append((fd, mode, settings)))
    setattr(termios, "TCSADRAIN", 1)
    setattr(tty, "setcbreak", lambda fd: None)
    monkeypatch.setitem(sys.modules, "termios", termios)
    monkeypatch.setitem(sys.modules, "tty", tty)
    monkeypatch.setattr(input_module.sys, "stdin", SimpleNamespace(fileno=lambda: 7))
    monkeypatch.setattr(input_module, "_read_linux_key", lambda fd: "\x03")
    with pytest.raises(KeyboardInterrupt):
        input_module.read_linux_input()
    assert calls == [(7, 1, [1, 2, 3])]
