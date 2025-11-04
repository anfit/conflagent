"""Utilities for producing consistent API response envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import jsonify


@dataclass(frozen=True)
class ResponseEnvelope:
    """Container describing the standard API response envelope."""

    success: bool
    code: str
    message: str
    data: Optional[Any]
    timestamp: str

    @classmethod
    def build(
        cls,
        success: bool,
        code: str,
        message: str,
        data: Optional[Any] = None,
    ) -> "ResponseEnvelope":
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return cls(success=success, code=code, message=message, data=data, timestamp=timestamp)

    def to_flask_response(self, status_code: int) -> Tuple[Any, int]:
        payload: Dict[str, Any] = {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return jsonify(payload), status_code


def success_response(
    message: str,
    data: Optional[Any] = None,
    *,
    code: str = "OK",
    status_code: int = 200,
) -> Tuple[Any, int]:
    envelope = ResponseEnvelope.build(True, code, message, data)
    return envelope.to_flask_response(status_code)


def error_response(
    code: str,
    message: str,
    *,
    status_code: int,
) -> Tuple[Any, int]:
    envelope = ResponseEnvelope.build(False, code, message, None)
    return envelope.to_flask_response(status_code)
