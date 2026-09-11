"""Request level guards that run before any view touches the body."""

from django.conf import settings
from django.http import JsonResponse

from apps.common.paths import is_mcp

MULTIPART_FRAMING_ALLOWANCE = 4096
METHODS_WITH_BODY = frozenset({"POST", "PUT", "PATCH"})


class RequestSizeLimitMiddleware:
    """Refuses an oversized request body before Django parses it."""

    def __init__(self, get_response):
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Answer 413 when the declared body exceeds the configured limit.

        Takes the request and returns either the refusal or the response of
        the rest of the chain. The size is read from the declared length
        rather than from the parsed upload: by the time a file is reachable on
        the request, Django has already streamed the whole body to disk, so a
        limit enforced there rejects the work only after doing all of it.

        A body sent without declaring its length is refused outright, because
        a chunked request carries no length to compare and would otherwise walk
        straight past the only limit there is. The MCP endpoint is the one
        exception: a streaming client is free to send exactly that kind of
        body, so only the demand for a length is lifted there. A declared
        length is still checked, and a chunked body sent to it stays bounded by
        the amount of non-file data Django will read at all, which is far below
        the upload limit this guards.
        """
        declared = request.META.get("CONTENT_LENGTH") or ""
        exempt = is_mcp(request.path)
        if request.method in METHODS_WITH_BODY and not declared.isdigit() and not exempt:
            return JsonResponse(
                {"detail": "A Content-Length header is required"},
                status=411,
            )
        if declared.isdigit():
            if int(declared) > settings.MAX_UPLOAD_BYTES + MULTIPART_FRAMING_ALLOWANCE:
                return JsonResponse(
                    {"detail": f"The request body exceeds the {settings.MAX_UPLOAD_BYTES} byte limit"},
                    status=413,
                )
        return self.get_response(request)
