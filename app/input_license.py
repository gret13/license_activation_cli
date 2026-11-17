import os
import select
import sys
from collections.abc import Callable

from app.config import Fields
from app.licensing import ALPHABET
from app.device import SYSTEM

PROMPT = "Введите лицензию (XXXX-XXXX-XXXX-XXXX): "


def format_license(characters: str, *, trailing_separator: bool = False) -> str:
    grouped = "-".join(
        characters[index : index + 4] for index in range(0, len(characters), 4)
    )
    if trailing_separator and len(characters) in (4, 8, 12):
        grouped += "-"
    return grouped


def read_windows_input(
    getwch: Callable[[], str],
    *,
    prompt: str = PROMPT,
) -> str:
    characters: list[str] = []
    last_display_length = 0
    print(prompt, end="", flush=True)

    while True:
        character = getwch()

        if character in ("\r", "\n"):
            break

        if character == "\x03":
            raise KeyboardInterrupt

        if character in ("\x00", "\xe0"):
            getwch()
            continue

        if character in ("\b", "\x7f"):
            if not characters:
                continue
            characters.pop()
        elif character in ALPHABET and len(characters) < 16:
            characters.append(character)
        else:
            continue

        entered = "".join(characters)
        display = format_license(entered, trailing_separator=True)

        print(
            "\r" + prompt + display + " " * max(last_display_length - len(display), 0),
            end="",
            flush=True,
        )
        last_display_length = len(display)

    print()
    return format_license("".join(characters))


def _read_linux_key(fd: int) -> str:
    character = os.read(fd, 1)

    if not character:
        raise EOFError

    if character == b"\x1b":
        if select.select([fd], [], [], 0.05)[0]:
            marker = os.read(fd, 1)

            if marker in (b"[", b"O"):
                while select.select([fd], [], [], 0.05)[0]:
                    following = os.read(fd, 1)

                    if not following or 0x40 <= following[0] <= 0x7E:
                        break

        return "\x1b"

    return character.decode("ascii", errors="ignore")


def read_linux_input(*, prompt: str = PROMPT) -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    original_settings = getattr(termios, "tcgetattr")(fd)

    try:
        getattr(tty, "setcbreak")(fd)

        return read_windows_input(
            lambda: _read_linux_key(fd),
            prompt=prompt,
        )
    finally:
        getattr(termios, "tcsetattr")(
            fd,
            getattr(termios, "TCSADRAIN"),
            original_settings,
        )


def input_license() -> str:
    if SYSTEM == Fields.windows:
        import msvcrt

        return read_windows_input(msvcrt.getwch)

    if SYSTEM == Fields.linux and sys.stdin.isatty():
        return read_linux_input()

    return input(PROMPT).strip()
