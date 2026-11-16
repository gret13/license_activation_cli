from dataclasses import dataclass
from typing import Any

import httpx

from app.config import ClientConfig, Fields, Message
from app.crypto import encrypt_payload
from app.licensing import license_hash


class ServerCommunicationError(Exception):
    pass


@dataclass(frozen=True)
class ApiResult:
    message: str
    success: bool


@dataclass(frozen=True)
class StatusCode:
    SUCCESS: int = 201
    BAD_REQUEST: int = 400
    PAYLOAD_TOO_LARGE: int = 413
    TOO_MANY_REQUESTS: int = 429
    INTERNAL_SERVER_ERROR: int = 500
    SERVICE_UNAVAILABLE: int = 503

    ALL = (
        SUCCESS,
        BAD_REQUEST,
        PAYLOAD_TOO_LARGE,
        TOO_MANY_REQUESTS,
        INTERNAL_SERVER_ERROR,
        SERVICE_UNAVAILABLE,
    )


@dataclass(frozen=True)
class StatusMessage:
    SUCCESS: str = "success"
    ERROR: str = "error"


@dataclass(frozen=True)
class Timeout:
    CONNECT: float = 5.0
    READ: float = 10.0
    WRITE: float = 10.0
    POOL: float = 5.0


def activate(
    config: ClientConfig, license_key: str, device: dict[str, object]
) -> ApiResult:
    message = {
        Fields.license_hash: license_hash(license_key),
        Fields.payload: encrypt_payload(license_key, device),
    }
    timeout = httpx.Timeout(
        connect=Timeout.CONNECT,
        read=Timeout.READ,
        write=Timeout.WRITE,
        pool=Timeout.POOL,
    )
    try:
        with httpx.Client(
            timeout=timeout, follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(config.url, json=message)
        if response.status_code not in StatusCode.ALL:
            raise ServerCommunicationError(Message.error.invalid_server_response)
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise ServerCommunicationError(Message.error.invalid_server_response)

        status = payload.get(Fields.status, "")
        message = payload.get(Fields.message, "")
        status_code = response.status_code

        if not (isinstance(status, str) and isinstance(message, str)):
            raise ServerCommunicationError(Message.error.invalid_server_response)

        if status_code == StatusCode.SUCCESS and status == StatusMessage.SUCCESS:
            return ApiResult(message=message, success=True)

        code = payload.get("code")
        if (
            status_code != StatusCode.SUCCESS
            and status == StatusMessage.ERROR
            and isinstance(code, str)
        ):
            return ApiResult(message=message, success=False)
        raise ServerCommunicationError(Message.error.invalid_server_response)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        raise ServerCommunicationError(Message.error.invalid_server_response) from exc
    except (ValueError, httpx.HTTPError) as exc:
        raise ServerCommunicationError(Message.error.invalid_server_response) from exc
