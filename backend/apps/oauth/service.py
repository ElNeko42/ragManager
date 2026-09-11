"""The decisions the authorization endpoints make, kept out of the views."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.agents.models import AgentToken
from apps.agents.tokens import hash_token, token_prefix
from apps.oauth import tokens
from apps.oauth.models import AuthorizationCode, RefreshToken


class OAuthError(Exception):
    """A failure that has to reach the caller as an OAuth error code."""

    def __init__(self, code, description, status=400):
        """Store the code the specification defines and a readable reason."""
        super().__init__(description)
        self.code = code
        self.description = description
        self.status = status


def issue_code(client, agent, redirect_uri, challenge, resource):
    """Record an approval and return the code that stands for it.

    Takes the client, the agent the owner approved it as, the address the code
    goes back to, the proof key challenge and the resource the token will be
    for. The code lives for a couple of minutes: it travels through a browser
    redirect, which is the least private part of the whole flow, so its window
    is the shortest thing here. Returns the code.
    """
    code = tokens.mint()
    AuthorizationCode.objects.create(
        code_hash=tokens.digest(code),
        client=client,
        agent=agent,
        redirect_uri=redirect_uri,
        code_challenge=challenge,
        resource=resource,
        expires_at=timezone.now() + timedelta(seconds=settings.OAUTH_CODE_LIFETIME_SECONDS),
    )
    return code


def redeem_code(client, code, verifier, redirect_uri, resource):
    """Turn an approval into a pair of tokens.

    Takes the client, the code, the proof key verifier, the address the code
    came back to and the resource asked for. Returns an (access token, refresh
    token, record) triple.

    A code that has already been spent is not merely refused: somebody other
    than the client is holding it, and since there is no way to tell which of
    the two is the impostor, everything that code produced is withdrawn.
    """
    record = AuthorizationCode.objects.filter(code_hash=tokens.digest(code)).first()
    if record is None or record.client_id != client.client_id:
        raise OAuthError("invalid_grant", "That code was not issued to this client")
    if record.used_at is not None:
        withdraw_everything_from(record)
        raise OAuthError("invalid_grant", "That code has already been used")
    if not record.is_usable():
        raise OAuthError("invalid_grant", "That code has expired")
    if record.redirect_uri != redirect_uri:
        raise OAuthError("invalid_grant", "The redirect address does not match the request")
    if not tokens.verify_challenge(verifier, record.code_challenge):
        raise OAuthError("invalid_grant", "The proof key does not match the request")
    if resource and resource.rstrip("/").lower() != record.resource.rstrip("/").lower():
        raise OAuthError("invalid_target", "The token was approved for another resource")

    with transaction.atomic():
        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])
        access, refresh = mint_pair(client, record.agent, record.resource, code=record)
    return access, refresh, record


def mint_pair(client, agent, resource, code=None, parent=None):
    """Mint an access token and the refresh token that replaces it.

    Takes the client, the agent it acts as, the resource the access token is
    for and, when this is a renewal, the code or the refresh token it descends
    from. The access token is an ordinary agent token carrying an audience, so
    the MCP endpoint authenticates it exactly as it does one typed into a
    configuration file. Returns the (access token, refresh token) pair.
    """
    access = tokens.mint(settings.OAUTH_TOKEN_PREFIX)
    stored = AgentToken.objects.create(
        agent=agent,
        token_hash=hash_token(access),
        token_prefix=token_prefix(access),
        expires_at=timezone.now()
        + timedelta(seconds=settings.OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS),
        issued_to=client,
        audience=resource,
    )
    refresh = tokens.mint(tokens.REFRESH_PREFIX)
    RefreshToken.objects.create(
        token_hash=tokens.digest(refresh),
        client=client,
        agent=agent,
        access_token=stored,
        resource=resource,
        code=code or (parent.code if parent else None),
        parent=parent,
        expires_at=timezone.now()
        + timedelta(seconds=settings.OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS),
    )
    return access, refresh


def rotate(client, refresh, resource):
    """Exchange a refresh token for a new pair, retiring the old one.

    Takes the client, the refresh token and the resource asked for. Returns the
    new (access token, refresh token) pair.

    Rotation is what makes a stolen refresh token detectable: the thief and the
    client cannot both use it, and whichever of them arrives second proves the
    copy exists. That second arrival withdraws the whole chain rather than
    guessing which one was the client.
    """
    record = RefreshToken.objects.filter(token_hash=tokens.digest(refresh)).first()
    if record is None or record.client_id != client.client_id:
        raise OAuthError("invalid_grant", "That refresh token was not issued to this client")
    if record.revoked_at is not None:
        withdraw_chain(record)
        raise OAuthError("invalid_grant", "That refresh token has already been used")
    if not record.is_valid():
        raise OAuthError("invalid_grant", "That refresh token has expired")
    if resource and resource.rstrip("/").lower() != record.resource.rstrip("/").lower():
        raise OAuthError("invalid_target", "That refresh token is for another resource")

    with transaction.atomic():
        retire(record)
        access, replacement = mint_pair(client, record.agent, record.resource, parent=record)
    return access, replacement


def retire(record):
    """Withdraw one refresh token and the access token it goes with."""
    now = timezone.now()
    record.revoked_at = now
    record.save(update_fields=["revoked_at"])
    if record.access_token and record.access_token.revoked_at is None:
        record.access_token.revoked_at = now
        record.access_token.save(update_fields=["revoked_at"])


def withdraw_chain(record):
    """Withdraw every token descended from the same original approval.

    Takes any refresh token in the chain. Walks to the first one and withdraws
    everything below it, because a token that turned up twice means the whole
    line of them is in somebody else's hands too.
    """
    root = record
    seen = set()
    while root.parent_id and root.parent_id not in seen:
        seen.add(root.pk)
        root = root.parent
    withdraw_below(root)


def withdraw_below(record):
    """Withdraw one refresh token and everything issued after it."""
    pending = [record]
    seen = set()
    while pending:
        node = pending.pop()
        if node.pk in seen:
            continue
        seen.add(node.pk)
        retire(node)
        pending.extend(node.children.all())


def withdraw_everything_from(code):
    """Withdraw every token a reused authorization code ever produced."""
    for refresh in code.refresh_tokens.all():
        withdraw_below(refresh)
