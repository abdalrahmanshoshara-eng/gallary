"""HTTP middleware."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .request_context import reset_request_id, sanitize_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware:
    """
    Attach a request id to every request.

    nginx forwards `X-Request-ID` (or generates one); when absent or malformed a new id
    is created. The id is exposed on the response and included in every log line.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.request_id = request_id  # type: ignore[attr-defined]
        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
