"""Minting and hashing of agent bearer tokens."""

import hashlib
import secrets

from django.views.decorators.debug import sensitive_variables

TOKEN_PREFIX = "rmg_"
PREFIX_LENGTH = 8
ENTROPY_BYTES = 32


@sensitive_variables()
def generate_token():
    """Mint a new bearer token.

    The result is shown to the operator once and never stored. Returns the
    token text, carrying a fixed prefix so that a leaked value is recognisable
    in logs and repositories.
    """
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(ENTROPY_BYTES)}"


@sensitive_variables()
def hash_token(token):
    """Hash a bearer token for storage and lookup.

    SHA-256 rather than a slow password hash: the token carries 256 bits of
    entropy, so stretching buys no resistance to guessing while it would
    forbid the indexed lookup every MCP request depends on. Returns the
    hexadecimal digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token):
    """Return the leading characters used to tell stored tokens apart.

    The prefix is not secret: it exists so the panel can show which token is
    which once the full value is unrecoverable.
    """
    return token[:PREFIX_LENGTH]


@sensitive_variables()
def issue_token(agent, expires_at=None):
    """Mint a token for an agent and store only its hash.

    Takes the agent and an optional expiry moment. Returns an (record, token)
    pair; the token text is the caller's only chance to read it, since nothing
    reversible reaches the database.
    """
    from apps.agents.models import AgentToken

    token = generate_token()
    record = AgentToken.objects.create(
        agent=agent,
        token_hash=hash_token(token),
        token_prefix=token_prefix(token),
        expires_at=expires_at,
    )
    return record, token
