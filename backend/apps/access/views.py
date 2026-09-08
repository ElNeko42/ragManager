"""Endpoints that grant and withdraw agent access."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.access.models import Permission, PermissionEffect
from apps.access.resolver import resolve_folder_effects
from apps.access.serializers import PermissionSerializer, PermissionUpdateSerializer
from apps.accounts.permissions import IsOwner
from apps.agents.models import Agent
from apps.drive.models import Document, Folder
from apps.common.validation import parse_uuid


class PermissionListCreateView(APIView):
    """Lists access rules and grants new ones."""

    permission_classes = [IsOwner]

    def get(self, request):
        """Return the access rules, narrowed to one agent when given."""
        permissions = Permission.objects.all()
        agent_id = request.query_params.get("agent")
        if agent_id:
            permissions = permissions.filter(agent_id=parse_uuid(agent_id, "agent"))
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


class EffectiveAccessView(APIView):
    """Shows what an agent actually ends up seeing, rules resolved."""

    permission_classes = [IsOwner]

    def get(self, request, agent_id):
        """Return the resolved permission of every folder for one agent.

        Takes the agent. Rules are inherited and the most specific one wins, so
        the rules written on a folder are not the answer to whether an agent
        reaches it; this walks the tree and reports the outcome, marking which
        folders decided it themselves and which inherited it. Document rules
        are listed too, since they override whatever their folder resolved to.
        """
        agent = get_object_or_404(Agent, pk=agent_id)
        effects = resolve_folder_effects(agent)
        own_rules = set(
            Permission.objects.filter(agent=agent, folder__isnull=False).values_list(
                "folder_id", flat=True
            )
        )
        folders = [
            {
                "folder_id": folder.pk,
                "name": folder.name,
                "parent": folder.parent_id,
                "collection": folder.collection_id,
                "effect": effects.get(folder.pk, PermissionEffect.DENY),
                "source": "own" if folder.pk in own_rules else "inherited",
            }
            for folder in Folder.objects.all()
        ]
        rules = Permission.objects.filter(agent=agent, document__isnull=False)
        names = dict(
            Document.objects.filter(
                pk__in=rules.values_list("document_id", flat=True)
            ).values_list("document_id", "name")
        )
        documents = [
            {
                "document_id": rule.document_id,
                "name": names.get(rule.document_id),
                "effect": rule.effect,
            }
            for rule in rules
        ]
        return Response({"folders": folders, "documents": documents})
