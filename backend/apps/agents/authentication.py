"""Bearer token authentication for external agents."""

from django.conf import settings
from django.views.decorators.debug import sensitive_variables
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.agents.models import AgentToken
from apps.common.paths import is_mcp
from apps.agents.tokens import hash_token

INVALID_TOKEN_MESSAGE = "Invalid token"


class AgentTokenAuthentication(BaseAuthentication):
    """Resolves the agent behind an Authorization bearer header."""

    keyword = "Bearer"

    @sensitive_variables()
    def authenticate(self, request):
        """Identify the agent that issued the request.

        Takes the incoming request. Returns an (agent, token) pair, or None
        when no bearer header is present so that session authentication may
        still run. Raises AuthenticationFailed for a token that is unknown,
        revoked or expired, reporting all three the same way so the caller
        learns nothing about which tokens exist.
        """
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise AuthenticationFailed("Malformed Authorization header")
        try:
            stored = AgentToken.objects.select_related("agent").get(
                token_hash=hash_token(header[1].decode())
            )
        except (AgentToken.DoesNotExist, UnicodeDecodeError):
            raise AuthenticationFailed(INVALID_TOKEN_MESSAGE)
        if not stored.is_valid():
            raise AuthenticationFailed(INVALID_TOKEN_MESSAGE)
        if not stored.is_for(self.resource(request)):
            raise AuthenticationFailed(INVALID_TOKEN_MESSAGE)
        return stored.agent, stored

    def resource(self, request):
        """Return what the caller is reaching for, as a token audience.

        A token approved through the authorization flow was bound to one
        resource, and presenting it anywhere else is exactly the replay the
        binding exists to stop. A token the owner issued by hand carries no
        audience and is not held to this.
        """
        base = request.build_absolute_uri("/").rstrip("/")
        if is_mcp(request.path):
            return f"{base}{settings.MCP_PATH}".rstrip("/")
        return f"{base}{request.path}"

    def authenticate_header(self, request):
        """Return the challenge sent alongside a 401 response.

        On the MCP endpoint the challenge names the document describing how to
        be authorized, which is how a client that arrived without a token finds
        its way into the flow rather than simply failing.
        """
        if not is_mcp(request.path):
            return self.keyword
        where = request.build_absolute_uri("/.well-known/oauth-protected-resource")
        return f'{self.keyword} resource_metadata="{where}"'
