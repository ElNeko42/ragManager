"""Endpoints that grant and withdraw agent access."""

from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.access.models import Permission, PermissionEffect
from apps.access.resolver import resolve_folder_effects
from apps.access.serializers import (
    PermissionFilterSerializer,
    PermissionSerializer,
    PermissionUpdateSerializer,
)
from apps.accounts.permissions import IsOwner
from apps.agents.models import Agent
from apps.drive.models import Document, Folder
from apps.drive.views import UUID_PATTERN


class PermissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Grants access rules, withdraws them and shows what they add up to."""

    queryset = Permission.objects.all()
    lookup_field = "permission_id"
    lookup_value_regex = UUID_PATTERN
    serializer_class = PermissionSerializer
    permission_classes = [IsOwner]

    def get_queryset(self):
        """Return the access rules, narrowed to one agent when given."""
        permissions = Permission.objects.all()
        filters = PermissionFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        agent = filters.validated_data.get("agent")
        if agent is not None:
            permissions = permissions.filter(agent_id=agent)
        return permissions

    def create(self, request, *args, **kwargs):
        """Grant or block one agent over one folder or one document.

        Takes the agent, the target and the effect. Rules are inherited down
        the tree and the most specific one wins, so a deny on a child overrides
        an allow on its parent. Returns the stored rule.
        """
        serializer = PermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = serializer.save()
        return Response(PermissionSerializer(permission).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Flip a rule between allowing and blocking its target."""
        permission = self.get_object()
        serializer = PermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission.effect = serializer.validated_data["effect"]
        permission.save(update_fields=["effect"])
        return Response(PermissionSerializer(permission).data)

    def destroy(self, request, *args, **kwargs):
        """Remove a rule, leaving the target to whatever it inherits."""
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["get"],
        url_path=f"effective/(?P<agent_id>{UUID_PATTERN})",
        url_name="effective",
    )
    def effective(self, request, agent_id=None):
        """Return the resolved permission of every folder for one agent.

        Takes the agent. Rules are inherited and the most specific one wins, so
        the rules written on a folder are not the answer to whether an agent
        reaches it; this walks the tree and reports the outcome, marking which
        folders decided it themselves and which inherited it. Document rules
        are listed too, since they override whatever their folder resolved to.

        The whole tree is reported, unpaged: this is the picture the owner
        checks a grant against, and a page of it would show an agent reaching
        a folder while hiding the deny written under it.
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
