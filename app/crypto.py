import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HKDF_SALT = b"license-activation-mvp"
HKDF_INFO = b"license-activation/aes-siv/v1"


def derive_key(license_key: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=64, salt=HKDF_SALT, info=HKDF_INFO
    ).derive(license_key.encode("utf-8"))


def encrypt_payload(license_key: str, device: dict[str, object]) -> str:
    plaintext = json.dumps(
        {"license_key": license_key, "device": device},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    ciphertext = AESSIV(derive_key(license_key)).encrypt(plaintext, [])
    return base64.b64encode(ciphertext).decode("ascii")
