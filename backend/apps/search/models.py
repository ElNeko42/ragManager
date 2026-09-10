"""The record of what agents asked this store for."""

import uuid

from django.db import models

from apps.agents.models import Agent
from apps.drive.models import Folder


class QuerySource(models.TextChoices):
    """Which door a query came through."""

    API = "api", "Search endpoint"
    MCP = "mcp", "MCP server"


class AgentQuery(models.Model):
    """One search made by one agent.

    The client of this system is an agent, so the questions it asks are the
    only account of what it was told and what it went looking for. Kept even
    when the search returned nothing, because a run of empty answers is
    usually the first sign that a permission is missing.

    The row outlives the agent's token but not the agent: deleting an agent
    withdraws its identity, and keeping its questions under a name that no
    longer resolves to anyone would leave a log nobody can act on.
    """

    query_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="queries")
    agent_name = models.CharField(max_length=100)
    query = models.TextField()
    source = models.CharField(max_length=8, choices=QuerySource.choices)
    folder = models.ForeignKey(
        Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name="queries"
    )
    limit = models.PositiveIntegerField()
    result_count = models.PositiveIntegerField()
    collections_searched = models.PositiveIntegerField()
    duration_ms = models.PositiveIntegerField()
    failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_queries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["agent", "-created_at"], name="agent_queries_agent_idx"),
            models.Index(fields=["-created_at"], name="agent_queries_recent_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=QuerySource.values),
                name="agent_queries_source_in_choices",
            )
        ]

    def __str__(self):
        """Return the agent and the opening of what it asked."""
        return f"{self.agent_name}: {self.query[:60]}"
