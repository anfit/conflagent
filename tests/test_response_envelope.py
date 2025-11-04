import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conflagent import app
from conflagent_core.response import ResponseEnvelope, error_response, success_response


def _parse_timestamp(value: str) -> datetime:
    """Convert a timestamp with trailing Z into a timezone-aware datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_response_envelope_build_produces_iso_timestamp():
    envelope = ResponseEnvelope.build(True, "OK", "done", data={"example": 1})

    assert envelope.success is True
    assert envelope.code == "OK"
    assert envelope.message == "done"
    assert envelope.data == {"example": 1}
    parsed_timestamp = _parse_timestamp(envelope.timestamp)
    assert parsed_timestamp.tzinfo is not None


def test_success_response_serialises_payload():
    with app.test_request_context():
        response, status_code = success_response("created", {"id": 1})

    assert status_code == 200
    payload = response.get_json()
    assert payload == {
        "success": True,
        "code": "OK",
        "message": "created",
        "data": {"id": 1},
        "timestamp": payload["timestamp"],
    }
    _parse_timestamp(payload["timestamp"])


def test_error_response_omits_data_field():
    with app.test_request_context():
        response, status_code = error_response("NOT_FOUND", "Missing", status_code=404)

    assert status_code == 404
    payload = response.get_json()
    assert payload == {
        "success": False,
        "code": "NOT_FOUND",
        "message": "Missing",
        "data": None,
        "timestamp": payload["timestamp"],
    }
    _parse_timestamp(payload["timestamp"])
