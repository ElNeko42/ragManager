"""External AI agents and the tokens they authenticate with."""

import uuid

from django.db import models
from django.utils import timezone


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

    @property
    def is_authenticated(self):
        """Report that a resolved agent counts as an authenticated principal.

        Django REST Framework asks this of whatever it puts on request.user,
        and an agent only ever reaches that attribute through a valid token.
        """
        return True


class AgentToken(models.Model):
    """A bearer credential issued to an agent.

    Only the hash is stored. The token itself is shown once at creation and is
    unrecoverable afterwards.

    One issued through the panel is good anywhere an agent may go. One issued
    to a connector through the authorization flow carries the audience it was
    approved for, and is refused anywhere else: a token minted for the MCP
    endpoint has no business being replayed against another resource, which is
    the whole reason the flow binds it to one.
    """

    token_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    token_prefix = models.CharField(max_length=8)
    issued_to = models.ForeignKey(
        "oauth.OAuthClient",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_tokens",
    )
    audience = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        """Return the agent name and the non secret token prefix."""
        return f"{self.agent.name} ({self.token_prefix}…)"

    def is_valid(self, at=None):
        """Report whether the token may still authenticate its agent.

        Takes the moment to evaluate, defaulting to now. Returns False once
        the token has been revoked or its expiry has passed.
        """
        moment = at or timezone.now()
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > moment

    def is_for(self, resource):
        """Report whether this token may be used against one resource.

        Takes the resource being reached for. A token with no audience was
        issued by the owner for the agent to use wherever it likes; one with
        an audience was approved for exactly that resource and nothing else.
        """
        if not self.audience:
            return True
        return self.audience.rstrip("/").lower() == resource.rstrip("/").lower()
