"""External AI agents and the tokens they authenticate with."""

import uuid

from django.db import models


class Agent(models.Model):
    """An external AI agent that queries the instance through MCP."""

    agent_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents"
        ordering = ["name"]

    def __str__(self):
        """Return the agent name."""
        return self.name


class AgentToken(models.Model):
    """A bearer credential issued to an agent.

    Only the hash is stored. The token itself is shown once at creation and is
    unrecoverable afterwards.
    """

    token_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    token_prefix = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        """Return the agent name and the non secret token prefix."""
        return f"{self.agent.name} ({self.token_prefix}…)"
