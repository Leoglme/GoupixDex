from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DesktopWorkerName = Literal["vinted", "amazon", "cardmarket", "leboncoin"]

#: Characters refused in a relayed worker path (header injection, fragments, other hosts).
_FORBIDDEN_PATH_CHARACTERS = ("\\", "\r", "\n", "\t", " ", "#")


def _validate_worker_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("path must be relative to the worker (start with a single '/')")
    if "://" in path or ".." in path or any(character in path for character in _FORBIDDEN_PATH_CHARACTERS):
        raise ValueError("path contains forbidden characters")
    return path


class DesktopRelayRequestIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    worker: DesktopWorkerName
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str = Field(min_length=1, max_length=2048)
    body: Any | None = None
    response_type: Literal["json", "blob"] = "json"
    timeout_ms: int | None = Field(default=None, ge=1_000, le=40 * 60_000)

    @field_validator("path")
    @classmethod
    def check_path(cls, value: str) -> str:
        return _validate_worker_path(value)


class DesktopRelayStreamIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    worker: DesktopWorkerName
    kind: Literal["sse", "ws"]
    path: str = Field(min_length=1, max_length=2048)

    @field_validator("path")
    @classmethod
    def check_path(cls, value: str) -> str:
        return _validate_worker_path(value)


class DesktopRelayResponseIn(BaseModel):
    request_id: str = Field(min_length=8, max_length=64)
    status: int = Field(ge=0, le=599)
    data: Any | None = None
    content_type: str | None = Field(default=None, max_length=200)
    encoding: Literal["json", "text", "base64"] = "json"
    error: str | None = Field(default=None, max_length=2000)


class DesktopRelayStreamEventIn(BaseModel):
    data: str
    event: str | None = Field(default=None, max_length=100)


class DesktopRelayStreamEventsIn(BaseModel):
    stream_id: str = Field(min_length=8, max_length=64)
    events: list[DesktopRelayStreamEventIn] = Field(min_length=1, max_length=500)


class DesktopRelayStreamEndIn(BaseModel):
    stream_id: str = Field(min_length=8, max_length=64)
    error: str | None = Field(default=None, max_length=2000)
