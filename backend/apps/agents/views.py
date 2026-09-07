"""Endpoints that manage agents and issue their bearer tokens."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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


class AgentListCreateView(APIView):
    """Lists the agents of the instance and registers new ones."""

    permission_classes = [IsOwner]

    def get(self, request):
        """Return every registered agent."""
        return Response(AgentSerializer(Agent.objects.all(), many=True).data)

    @sensitive_variables()
    def post(self, request):
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


class AgentDetailView(APIView):
    """Removes an agent and everything issued to it."""

    permission_classes = [IsOwner]

    def delete(self, request, agent_id):
        """Delete an agent along with its tokens and access rules.

        Returns 204 once the agent can no longer reach the instance.
        """
        get_object_or_404(Agent, pk=agent_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentTokenListCreateView(APIView):
    """Lists the tokens of an agent and mints replacements."""

    permission_classes = [IsOwner]

    def get(self, request, agent_id):
        """Return the tokens of an agent, without ever exposing their value."""
        agent = get_object_or_404(Agent, pk=agent_id)
        return Response(AgentTokenSerializer(agent.tokens.all(), many=True).data)

    @sensitive_variables()
    def post(self, request, agent_id):
        """Mint an additional token for an agent.

        Takes an optional expiry. Returns the token text once; existing tokens
        keep working, so revoking the old one is a separate deliberate step.
        """
        agent = get_object_or_404(Agent, pk=agent_id)
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record, token = issue_token(agent, serializer.validated_data.get("expires_at"))
        return Response(
            {"token": token, "token_detail": AgentTokenSerializer(record).data},
            status=status.HTTP_201_CREATED,
        )


class AgentTokenRevokeView(APIView):
    """Revokes a single token without deleting its trace."""

    permission_classes = [IsOwner]

    def post(self, request, agent_id, token_id):
        """Revoke a token immediately.

        The row survives so that the panel can still show the token existed.
        Returns the updated token, or 404 when it does not belong to the agent.
        """
        token = get_object_or_404(AgentToken, pk=token_id, agent_id=agent_id)
        if token.revoked_at is None:
            token.revoked_at = timezone.now()
            token.save(update_fields=["revoked_at"])
        return Response(AgentTokenSerializer(token).data)


class AgentIdentityView(APIView):
    """Lets an agent confirm which identity its token resolves to."""

    permission_classes = [IsAgent]

    def get(self, request):
        """Return the agent behind the bearer token used for this request."""
        return Response(AgentSerializer(request.user).data)
