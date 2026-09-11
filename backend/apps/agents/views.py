"""Endpoints that manage agents and issue their bearer tokens."""

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOwner
from apps.agents.models import Agent, AgentToken
from apps.agents.permissions import IsAgent
from apps.agents.serializers import (
    AgentCreateSerializer,
    AgentSerializer,
    AgentTokenSerializer,
    TokenRequestSerializer,
)
from apps.agents.tokens import issue_token
from apps.drive.views import UUID_PATTERN


class AgentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Registers agents, issues their tokens and takes them away again."""

    queryset = Agent.objects.all()
    lookup_field = "agent_id"
    lookup_value_regex = UUID_PATTERN
    serializer_class = AgentSerializer
    permission_classes = [IsOwner]

    def get_permissions(self):
        """Let an agent reach the one route that is about itself.

        Everything here is the owner's, except the identity route: that one is
        how an agent confirms which name its token resolves to, so it is the
        only one an agent token may enter.
        """
        if self.action == "identity":
            return [IsAgent()]
        return super().get_permissions()

    @sensitive_variables()
    def create(self, request, *args, **kwargs):
        """Register an agent and mint its first token.

        Takes a name and an optional expiry. Returns the agent together with
        the token text, which is shown here and nowhere else again.
        """
        serializer = AgentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            agent = Agent.objects.create(name=serializer.validated_data["name"])
            record, token = issue_token(agent, serializer.validated_data.get("expires_at"))
        return Response(
            {
                "agent": AgentSerializer(agent).data,
                "token": token,
                "token_detail": AgentTokenSerializer(record).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """Delete an agent along with its tokens and access rules.

        Returns 204 once the agent can no longer reach the instance.
        """
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="connection", url_name="connection")
    def connection(self, request):
        """Return the address an agent connects its MCP client to.

        The panel cannot work this out for itself: it is served from the same
        host as the API in production but from a development server in front of
        it otherwise, and the MCP endpoint is not the one it would guess in the
        second case. Built from the request, so an instance behind a proxy
        reports the address its agents can actually reach rather than the one
        the container sees.
        """
        return Response({"url": request.build_absolute_uri(settings.MCP_PATH)})

    @action(detail=False, methods=["get"], url_path="me", url_name="identity")
    def identity(self, request):
        """Return the agent behind the bearer token used for this request."""
        return Response(AgentSerializer(request.user).data)

    @action(detail=True, methods=["get", "post"], url_path="tokens", url_name="token-list")
    def tokens(self, request, *args, **kwargs):
        """List the tokens of an agent, or mint another one."""
        if request.method == "POST":
            return self.mint_token(request)
        agent = self.get_object()
        page = self.paginate_queryset(agent.tokens.all())
        return self.get_paginated_response(AgentTokenSerializer(page, many=True).data)

    @sensitive_variables()
    def mint_token(self, request):
        """Mint an additional token for an agent.

        Takes an optional expiry. Returns the token text once; existing tokens
        keep working, so revoking the old one is a separate deliberate step.
        """
        agent = self.get_object()
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record, token = issue_token(agent, serializer.validated_data.get("expires_at"))
        return Response(
            {"token": token, "token_detail": AgentTokenSerializer(record).data},
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path=f"tokens/(?P<token_id>{UUID_PATTERN})/revoke",
        url_name="token-revoke",
    )
    def revoke(self, request, token_id=None, **kwargs):
        """Revoke a token immediately.

        The row survives so that the panel can still show the token existed.
        Returns the updated token, or 404 when it does not belong to the agent.
        """
        token = get_object_or_404(AgentToken, pk=token_id, agent=self.get_object())
        if token.revoked_at is None:
            token.revoked_at = timezone.now()
            token.save(update_fields=["revoked_at"])
        return Response(AgentTokenSerializer(token).data)
