import base64
import json

from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from app.crypto import derive_key, encrypt_payload
from app.licensing import checksum_value, license_hash, valid_license

EXPECTED_KEY_HEX = (
    "c585cbac48e6c830910cc37d64f6809757fd2accbf6d2bda12ba45766a4d917e"
    "d55f9be3f236e76729e4d10618ceda9efd9a0c4db0c2e5bb51ff2f4e66b77470"
)
EXPECTED_PAYLOAD = (
    "Y6jsK0b1XQ4YgKFMR3y+jKzvD4dMROD/HhsqG5mLY++Z15mwxP4+hvxq/E/rJ9Ng89xFpG2Pbq3oH/"
    "PYY9k3zB5dnNN8YfuC/T9KH6Kd2AFUqyV5ZyqPlcO4FJwYuPumVvgSC7s+f3fJ3vGqRfzsWCHSmhO3"
    "rI91tFyscAcGy4OomwAP7uRmMTdr5bBAMpWrQd5SU7LhPnU3STfyuHSaGtSo6b9xVGgwEhjtNOAOwFrSpouA"
)


def test_luhn_mod62(license_key: str) -> None:
    assert checksum_value(license_key.replace("-", "")) == 0
    assert valid_license(license_key)
    assert not valid_license("Ds23-Da34-We21-E335")
    assert not valid_license(license_key.lower())
    assert not valid_license("Ds23-Da34-We21-E33")
    distinct_licenses = (
        "ds23-da34-we21-e33f",
        "Ds23-Da34-We21-E334",
        "DS23-DA34-WE21-E33K",
    )
    assert all(valid_license(key) for key in distinct_licenses)
    assert len({license_hash(key) for key in distinct_licenses}) == 3
    assert not valid_license("ds23-da34-we21-e334")


def test_compatible_crypto_test_vector(
    license_key: str, device_data: dict[str, object]
) -> None:
    assert derive_key(license_key).hex() == EXPECTED_KEY_HEX
    assert encrypt_payload(license_key, device_data) == EXPECTED_PAYLOAD
    assert encrypt_payload(license_key, device_data) == encrypt_payload(license_key, device_data)
    assert len(license_hash(license_key)) == 64


def test_encrypted_payload_contains_expected_data(
    license_key: str, device_data: dict[str, object]
) -> None:
    ciphertext = base64.b64decode(encrypt_payload(license_key, device_data), validate=True)
    plaintext = AESSIV(derive_key(license_key)).decrypt(ciphertext, [])
    assert json.loads(plaintext) == {"license_key": license_key, "device": device_data}


def test_changes_to_license_or_device_change_ciphertext(
    license_key: str, device_data: dict[str, object]
) -> None:
    altered_device = {**device_data, "cpu_cores": 16}
    assert encrypt_payload(license_key, device_data) != encrypt_payload(
        license_key, altered_device
    )
    assert derive_key(license_key) != derive_key(license_key.swapcase())
