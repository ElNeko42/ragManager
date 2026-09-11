"""The clients, codes and refresh tokens of the authorization server.

An access token is not here: it is an AgentToken like any other, because the
whole point of this flow is to end up with the same credential the panel
issues by hand. Everything downstream — the permission resolver, the record of
what was searched, the rate limit — then works without knowing which of the
two doors minted it.
"""

import uuid

from django.db import models
from django.utils import timezone

from apps.agents.models import Agent


class OAuthClient(models.Model):
    """A program that may ask to act as one of this instance's agents.

    Registering says nothing about access: a client holds no permission of its
    own and reaches nothing until the owner approves it against an agent, and
    what it may then read is whatever that agent was granted.
    """

    client_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    secret_hash = models.CharField(max_length=64, blank=True, default="")
    redirect_uris = models.JSONField(default=list)
    registered_dynamically = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "oauth_clients"
        ordering = ["-created_at"]

    def __str__(self):
        """Return the name the client registered under."""
        return self.name

    @property
    def is_confidential(self):
        """Report whether this client proves who it is with a secret."""
        return bool(self.secret_hash)

    def allows(self, redirect_uri):
        """Report whether a redirect address was registered by this client.

        Takes the address. Compared exactly rather than by prefix or by host:
        an attacker who can bend the redirect anywhere inside a registered
        origin can walk off with the authorization code.
        """
        return redirect_uri in self.redirect_uris


class AuthorizationCode(models.Model):
    """One approval, waiting to be exchanged for a token.

    Only the hash is stored: the code itself travels through a browser
    redirect and a database anyone can read must not hold something that could
    be replayed from it.
    """

    code_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE, related_name="codes")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="codes")
    redirect_uri = models.CharField(max_length=2000)
    code_challenge = models.CharField(max_length=128)
    resource = models.CharField(max_length=500)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "oauth_codes"
        ordering = ["-created_at"]

    def __str__(self):
        """Return the client and the agent the approval was for."""
        return f"{self.client.name} as {self.agent.name}"

    def is_usable(self, at=None):
        """Report whether this code may still be exchanged.

        Takes the moment to evaluate. A code is good once and briefly: a second
        exchange means somebody other than the client has it, which is why the
        reuse is answered by throwing away everything it produced rather than
        by quietly refusing.
        """
        moment = at or timezone.now()
        return self.used_at is None and self.expires_at > moment


class RefreshToken(models.Model):
    """A credential for replacing an access token that has expired.

    Rotated on every use. A refresh token that turns up twice has been copied,
    and since there is no way to tell the thief from the client, the whole
    chain descended from the first one is withdrawn.
    """

    refresh_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True)
    client = models.ForeignKey(OAuthClient, on_delete=models.CASCADE, related_name="refresh_tokens")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="refresh_tokens")
    access_token = models.ForeignKey(
        "agents.AgentToken",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refreshes",
    )
    resource = models.CharField(max_length=500)
    code = models.ForeignKey(
        AuthorizationCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refresh_tokens",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "oauth_refresh_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        """Return the client and the agent this refresh belongs to."""
        return f"{self.client.name} as {self.agent.name}"

    def is_valid(self, at=None):
        """Report whether this refresh token may still be exchanged."""
        moment = at or timezone.now()
        return self.revoked_at is None and self.expires_at > moment
