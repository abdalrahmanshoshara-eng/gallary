import logging

from apps.core.logging import RequestIdFilter
from apps.core.request_context import reset_request_id, set_request_id


def test_valid_incoming_request_id_is_echoed(client):
    response = client.get("/api/v1/health/live", HTTP_X_REQUEST_ID="abc12345-from-nginx")
    assert response["X-Request-ID"] == "abc12345-from-nginx"


def test_malformed_request_id_is_replaced(client):
    response = client.get("/api/v1/health/live", HTTP_X_REQUEST_ID="<script>")
    assert response["X-Request-ID"] != "<script>"
    assert len(response["X-Request-ID"]) == 32


def test_log_records_carry_current_request_id():
    token = set_request_id("req-1234567")
    try:
        record = logging.LogRecord("x", logging.INFO, "", 0, "msg", None, None)
        RequestIdFilter().filter(record)
        assert record.request_id == "req-1234567"
    finally:
        reset_request_id(token)
