"""Access rules granted to agents over folders and documents."""

import uuid

from django.db import models

from apps.agents.models import Agent
from apps.drive.models import Document, Folder


class PermissionEffect(models.TextChoices):
    """Whether a rule opens or closes access to its target."""

    ALLOW = "allow", "Allow"
    DENY = "deny", "Deny"


class Permission(models.Model):
    """One access rule for one agent over one folder or one document.

    Rules are inherited down the folder tree and the most specific one wins: a
    document rule beats any folder rule, and the nearest ancestor with a rule
    beats the ones above it. An agent with no rule on the whole path is denied.
    """

    permission_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="permissions")
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True, related_name="permissions"
    )
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, null=True, blank=True, related_name="permissions"
    )
    effect = models.CharField(max_length=8, choices=PermissionEffect.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        # The panel reads these a page at a time, and a page of an unordered
        # table can skip a rule or show one twice between two requests.
        ordering = ["-created_at", "permission_id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(folder__isnull=False, document__isnull=True)
                    | models.Q(folder__isnull=True, document__isnull=False)
                ),
                name="permissions_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["agent", "folder"],
                condition=models.Q(folder__isnull=False),
                name="permissions_unique_agent_folder",
            ),
            models.UniqueConstraint(
                fields=["agent", "document"],
                condition=models.Q(document__isnull=False),
                name="permissions_unique_agent_document",
            ),
            models.CheckConstraint(
                condition=models.Q(effect__in=PermissionEffect.values),
                name="permissions_effect_in_choices",
            ),
        ]

    def __str__(self):
        """Return the rule as agent, effect and target."""
        return f"{self.agent.name} {self.effect} {self.folder or self.document}"
