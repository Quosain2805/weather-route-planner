from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services.errors import NoRouteError, UpstreamError


def api_exception_handler(exc, context):
    """Same {"error": {code, message, fields?}} envelope for every failure, validation included."""
    if isinstance(exc, NoRouteError):
        return _envelope("no_route", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, UpstreamError):
        return _envelope("upstream_unavailable", exc.message, exc.status)

    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    if response.status_code == 400 and isinstance(detail, dict):
        response.data = {
            "error": {"code": "validation_error", "message": _first_message(detail), "fields": detail}
        }
    else:
        message = detail.get("detail") if isinstance(detail, dict) else detail
        response.data = {"error": {"code": "error", "message": _first_message(message)}}
    return response


def _envelope(code: str, message: str, http_status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=http_status)


def _first_message(node) -> str:
    """Dig the first human-readable string out of DRF's nested error structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            text = _first_message(value)
            if text:
                return text if key in ("non_field_errors", "detail") else f"{key}: {text}"
        return ""
    if isinstance(node, (list, tuple)):
        for item in node:
            text = _first_message(item)
            if text:
                return text
        return ""
    return str(node)
