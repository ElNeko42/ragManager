"""Permission classes for endpoints reserved to agents."""

from rest_framework.permissions import BasePermission

from apps.agents.models import Agent


class IsAgent(BasePermission):
    """Allows only requests authenticated with an agent token."""

    def has_permission(self, request, view):
        """Report whether an agent, and not the owner, made this request."""
        return isinstance(request.user, Agent)
