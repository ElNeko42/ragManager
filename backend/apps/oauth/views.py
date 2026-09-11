"""The endpoints of the authorization server and the screen the owner sees."""

import base64
import json
import logging
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from apps.accounts.models import User
from apps.agents.models import Agent
from apps.oauth import metadata, service, tokens
from apps.oauth.models import OAuthClient

logger = logging.getLogger(__name__)

MAX_REDIRECT_URIS = 10
S256 = "S256"


def protected_resource(request):
    """Publish where a client should go to be authorized.

    This is the document a refused client reads, and the only thing tying the
    MCP endpoint to the server that issues its tokens.
    """
    return JsonResponse(metadata.protected_resource(request))


def authorization_server(request):
    """Publish how the authorization flow works here."""
    return JsonResponse(metadata.authorization_server(request))


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(View):
    """Lets a client obtain an identity without anyone typing it in.

    Registering grants nothing. A client that has registered may ask, and the
    owner is the one who answers: until that approval it reaches no document,
    no agent and no folder. The cross site check is lifted because the caller
    is a program with no cookies here, and there is no session for a forged
    request to ride on.
    """

    def post(self, request):
        """Register a client and return the identity it should use."""
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return error("invalid_client_metadata", "The body is not valid JSON")
        if not isinstance(payload, dict):
            return error("invalid_client_metadata", "The body has to be an object")

        uris = payload.get("redirect_uris")
        if not isinstance(uris, list) or not uris:
            return error("invalid_redirect_uri", "At least one redirect address is required")
        if len(uris) > MAX_REDIRECT_URIS:
            return error("invalid_redirect_uri", "Too many redirect addresses")
        for uri in uris:
            if not isinstance(uri, str) or not is_safe_redirect(uri):
                return error(
                    "invalid_redirect_uri",
                    "A redirect address has to be https, or http on localhost",
                )

        wants_secret = payload.get("token_endpoint_auth_method", "none") != "none"
        secret = tokens.mint() if wants_secret else ""
        client = OAuthClient.objects.create(
            name=str(payload.get("client_name") or "Unnamed client")[:200],
            redirect_uris=uris,
            secret_hash=tokens.digest(secret) if secret else "",
            registered_dynamically=True,
        )
        body = {
            "client_id": str(client.client_id),
            "client_name": client.name,
            "redirect_uris": client.redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post" if secret else "none",
            "client_id_issued_at": int(client.created_at.timestamp()),
        }
        if secret:
            body["client_secret"] = secret
        return JsonResponse(body, status=201)


def sign_in_first(request):
    """Return where to send somebody who has to sign in before approving.

    The address they were heading to is encoded rather than appended raw: it
    carries a query of its own, and pasted in whole its parameters would be
    read as belonging to the panel instead, which loses the request they were
    in the middle of.
    """
    return f"/?{urlencode({'next': request.get_full_path()})}"


def is_safe_redirect(uri):
    """Report whether a redirect address may be registered at all.

    Anything but https is refused, except on the loopback address, which is
    where a client running on the same machine as its user has to listen. An
    address that is not one of those carries the authorization code over a
    network in the clear.
    """
    parsed = urlparse(uri)
    if parsed.fragment:
        return False
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    if parsed.scheme == "http":
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    return False


class AuthorizeView(View):
    """Asks the owner whether a client may act as one of their agents."""

    def get(self, request):
        """Show the approval screen, or say why it cannot be shown.

        A request naming a client or a redirect address that does not check out
        is answered on this page rather than by redirecting: sending a browser
        to an address the client never registered is the attack the check
        exists to prevent.
        """
        try:
            ask = self.read(request)
        except service.OAuthError as failure:
            return self.refuse(request, failure)
        if not isinstance(request.user, User):
            return redirect(sign_in_first(request))
        return render(request, "oauth/consent.html", self.screen(request, ask))

    @method_decorator(csrf_protect)
    @method_decorator(sensitive_post_parameters())
    def post(self, request):
        """Record the owner's answer and send the browser back to the client."""
        try:
            ask = self.read(request)
        except service.OAuthError as failure:
            return self.refuse(request, failure)
        if not isinstance(request.user, User):
            return redirect(sign_in_first(request))
        if request.POST.get("decision") != "approve":
            return redirect(self.back(ask, {"error": "access_denied"}))

        agent = Agent.objects.filter(pk=request.POST.get("agent")).first()
        if agent is None:
            screen = self.screen(request, ask)
            screen["problem"] = "Choose which agent this connector should act as"
            return render(request, "oauth/consent.html", screen, status=400)

        code = service.issue_code(
            ask["client"], agent, ask["redirect_uri"], ask["challenge"], ask["resource"]
        )
        return redirect(self.back(ask, {"code": code}))

    def read(self, request):
        """Pull the authorization request apart and check every piece of it."""
        data = request.POST if request.method == "POST" else request.GET
        client = OAuthClient.objects.filter(pk=valid_uuid(data.get("client_id"))).first()
        if client is None:
            raise service.OAuthError("invalid_client", "No client is registered under that id")
        redirect_uri = data.get("redirect_uri") or ""
        if not client.allows(redirect_uri):
            raise service.OAuthError(
                "invalid_request", "That redirect address is not registered for this client"
            )
        if data.get("response_type") != "code":
            raise service.OAuthError("unsupported_response_type", "Only the code flow is offered")
        if data.get("code_challenge_method", S256) != S256:
            raise service.OAuthError("invalid_request", "Only the S256 proof key is accepted")
        challenge = data.get("code_challenge") or ""
        if not challenge:
            raise service.OAuthError("invalid_request", "A proof key challenge is required")
        resource = data.get("resource") or ""
        if not metadata.same_resource(resource, request):
            raise service.OAuthError("invalid_target", "This server cannot issue a token for that")
        return {
            "client": client,
            "redirect_uri": redirect_uri,
            "challenge": challenge,
            "resource": metadata.canonical_resource(request),
            "state": data.get("state") or "",
        }

    def screen(self, request, ask):
        """Build what the approval page shows."""
        return {
            "client_name": ask["client"].name,
            "resource": ask["resource"],
            "agents": Agent.objects.all(),
            "fields": {
                "client_id": str(ask["client"].client_id),
                "redirect_uri": ask["redirect_uri"],
                "response_type": "code",
                "code_challenge": ask["challenge"],
                "code_challenge_method": S256,
                "resource": ask["resource"],
                "state": ask["state"],
            },
            "problem": None,
        }

    def back(self, ask, extra):
        """Build the address the browser returns to, carrying the answer."""
        parameters = dict(extra)
        if ask["state"]:
            parameters["state"] = ask["state"]
        joiner = "&" if "?" in ask["redirect_uri"] else "?"
        return f"{ask['redirect_uri']}{joiner}{urlencode(parameters)}"

    def refuse(self, request, failure):
        """Explain a request that cannot be answered by redirecting anywhere."""
        return render(
            request,
            "oauth/refused.html",
            {"code": failure.code, "description": failure.description},
            status=failure.status,
        )


@method_decorator(csrf_exempt, name="dispatch")
class TokenView(View):
    """Exchanges an approval, or a refresh token, for a fresh pair."""

    @method_decorator(sensitive_post_parameters())
    @method_decorator(sensitive_variables())
    def post(self, request):
        """Answer a token request of either grant this server offers."""
        try:
            client = self.identify(request)
            grant = request.POST.get("grant_type")
            if grant == "authorization_code":
                access, refresh, _ = service.redeem_code(
                    client,
                    request.POST.get("code") or "",
                    request.POST.get("code_verifier") or "",
                    request.POST.get("redirect_uri") or "",
                    request.POST.get("resource") or "",
                )
            elif grant == "refresh_token":
                access, refresh = service.rotate(
                    client,
                    request.POST.get("refresh_token") or "",
                    request.POST.get("resource") or "",
                )
            else:
                raise service.OAuthError("unsupported_grant_type", "That grant is not offered")
        except service.OAuthError as failure:
            return error(failure.code, failure.description, failure.status)
        return JsonResponse(
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": settings.OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
                "refresh_token": refresh,
            },
            headers={"Cache-Control": "no-store"},
        )

    @sensitive_variables()
    def identify(self, request):
        """Work out which client is asking, and that it is entitled to.

        A client that registered a secret has to present it; one that did not
        is a public client and proves itself with the proof key instead, which
        is what the flow is built around.
        """
        client_id, secret = self.credentials(request)
        client = OAuthClient.objects.filter(pk=valid_uuid(client_id)).first()
        if client is None:
            raise service.OAuthError("invalid_client", "No client is registered under that id", 401)
        if client.is_confidential and not tokens.verify(secret or "", client.secret_hash):
            raise service.OAuthError("invalid_client", "The client secret does not match", 401)
        return client

    @sensitive_variables()
    def credentials(self, request):
        """Read the client's identity from the header or from the body."""
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
                name, _, secret = decoded.partition(":")
                return name, secret
            except (ValueError, UnicodeDecodeError):
                raise service.OAuthError("invalid_client", "The header cannot be read", 401)
        return request.POST.get("client_id"), request.POST.get("client_secret")


def valid_uuid(value):
    """Return a value that can be looked up as an identifier, or nothing."""
    import uuid

    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def error(code, description, status=400):
    """Answer with the error shape the specification defines."""
    return JsonResponse(
        {"error": code, "error_description": description},
        status=status,
        headers={"Cache-Control": "no-store"},
    )
