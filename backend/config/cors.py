"""Which addresses a browser on any site may call.

The panel is served from one origin and its API answers only that origin,
which is what CORS_ALLOWED_ORIGINS says. The MCP endpoint and the
authorization flow around it are a different case: the caller is a program
that identifies itself with a bearer token or a proof key, not with a cookie,
and it may well be running inside a browser on a site this server has never
heard of. Refusing it there tells it nothing except that no server answers.
"""

from apps.common.paths import is_mcp

OPEN_PATHS = frozenset(
    {
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-authorization-server",
        "/oauth/register/",
        "/oauth/token/",
    }
)


def is_open_to_any_origin(path):
    """Report whether an address answers a browser from any origin.

    Takes the path of a request. The approval screen is deliberately absent:
    it is the one page of the flow that acts on the owner's session cookie,
    and a cross site call to it is exactly what the cookie rules exist to
    refuse.
    """
    return is_mcp(path) or path in OPEN_PATHS


def allow_any_origin(sender, request, **kwargs):
    """Answer the CORS check for the addresses that take any origin."""
    return is_open_to_any_origin(request.path)


def connect():
    """Register the check with the CORS middleware, once the apps are ready."""
    from corsheaders.signals import check_request_enabled

    check_request_enabled.connect(allow_any_origin, dispatch_uid="ragmanager-open-cors")
