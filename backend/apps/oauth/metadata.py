"""What this server publishes about itself, and the name it answers to."""

from django.conf import settings
from django.urls import reverse


def issuer(request):
    """Return the address this authorization server is known by.

    Everything it publishes has to agree with the address the client actually
    reached, or a client that validates the issuer refuses the metadata it
    just downloaded.
    """
    return request.build_absolute_uri("/").rstrip("/")


def canonical_resource(request):
    """Return the identifier of the MCP endpoint as a resource.

    Tokens are bound to this, and a token presented with any other audience is
    refused. Written without the trailing slash, which is the form the
    specification asks implementations to settle on.
    """
    return f"{issuer(request)}{settings.MCP_PATH}".rstrip("/")


def same_resource(asked, request):
    """Report whether a client is asking for a token for this server.

    Takes what the client named and the request it arrived on. A missing name
    is accepted, since the token is bound to this server either way; a name
    that points somewhere else is not, because issuing it would hand the
    client a credential for a resource this server has no business speaking
    for. The trailing slash is not a difference worth refusing over.
    """
    if not asked:
        return True
    return asked.rstrip("/").lower() == canonical_resource(request).lower()


def protected_resource(request):
    """Return the document that tells a client where to get a token.

    This is what a client reads after being refused, and the only thing that
    connects the MCP endpoint to the server that authorizes it.
    """
    return {
        "resource": canonical_resource(request),
        "authorization_servers": [issuer(request)],
        "bearer_methods_supported": ["header"],
        "resource_name": "ragManager document store",
    }


def authorization_server(request):
    """Return the document that tells a client how to run the flow.

    Only S256 is offered for the proof key: the plain method proves nothing
    against an attacker who can see the authorization request, which is the
    attack the proof key exists to stop.
    """
    base = issuer(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}{reverse('oauth-authorize')}",
        "token_endpoint": f"{base}{reverse('oauth-token')}",
        "registration_endpoint": f"{base}{reverse('oauth-register')}",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": [
            "none",
            "client_secret_post",
            "client_secret_basic",
        ],
    }
