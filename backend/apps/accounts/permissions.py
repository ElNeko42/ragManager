"""Permission classes for endpoints reserved to the owner."""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsOwner(BasePermission):
    """Allows only requests made from the owner's browser session.

    An agent token authenticates a principal too, so checking for a signed in
    user is not enough: management endpoints must reject agents explicitly.
    """

    def has_permission(self, request, view):
        """Report whether the owner, and not an agent, made this request."""
        return isinstance(request.user, User)
