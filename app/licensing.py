import hashlib
import re
import string


ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase
BASE = len(ALPHABET)
CHAR_TO_VALUE = {character: value for value, character in enumerate(ALPHABET)}
PATTERN = re.compile(r"[A-Za-z0-9]{4}(?:-[A-Za-z0-9]{4}){3}\Z", re.ASCII)


def checksum_value(text: str) -> int:
    total = 0
    factor = 1
    for character in reversed(text):
        addend = factor * CHAR_TO_VALUE[character]
        total += addend // BASE + addend % BASE
        factor = 3 - factor
    return total % BASE


def valid_license(key: str) -> bool:
    return PATTERN.fullmatch(key) is not None and checksum_value(key.replace("-", "")) == 0


def license_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
