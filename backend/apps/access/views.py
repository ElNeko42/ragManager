"""Endpoints that grant and withdraw agent access."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.access.models import Permission
from apps.access.serializers import PermissionSerializer, PermissionUpdateSerializer
from apps.accounts.permissions import IsOwner


class PermissionListCreateView(APIView):
    """Lists access rules and grants new ones."""

    permission_classes = [IsOwner]

    def get(self, request):
        """Return the access rules, narrowed to one agent when given."""
        permissions = Permission.objects.all()
        agent_id = request.query_params.get("agent")
        if agent_id:
            permissions = permissions.filter(agent_id=agent_id)
        return Response(PermissionSerializer(permissions, many=True).data)

    def post(self, request):
        """Grant or block one agent over one folder or one document.

        Takes the agent, the target and the effect. Rules are inherited down
        the tree and the most specific one wins, so a deny on a child overrides
        an allow on its parent. Returns the stored rule.
        """
        serializer = PermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = serializer.save()
        return Response(PermissionSerializer(permission).data, status=status.HTTP_201_CREATED)


class PermissionDetailView(APIView):
    """Flips and removes a single access rule."""

    permission_classes = [IsOwner]

    def patch(self, request, permission_id):
        """Flip a rule between allowing and blocking its target."""
        permission = get_object_or_404(Permission, pk=permission_id)
        serializer = PermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission.effect = serializer.validated_data["effect"]
        permission.save(update_fields=["effect"])
        return Response(PermissionSerializer(permission).data)

    def delete(self, request, permission_id):
        """Remove a rule, leaving the target to whatever it inherits."""
        get_object_or_404(Permission, pk=permission_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
