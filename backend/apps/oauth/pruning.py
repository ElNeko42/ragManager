"""Throwing away what the authorization flow no longer needs.

Every registration, approval and renewal leaves a row behind, and a server
open to the internet is registered with by anyone who feels like it. Nothing
here is needed once it has expired, been used or been withdrawn; keeping it
costs space and, for the clients, leaves a table that grows with every
stranger who found the endpoint.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.agents.models import AgentToken
from apps.oauth.models import AuthorizationCode, OAuthClient, RefreshToken

SPENT_CODE_GRACE = timedelta(hours=1)
DEAD_TOKEN_GRACE = timedelta(days=7)
UNUSED_CLIENT_GRACE = timedelta(hours=24)


def prune(now=None):
    """Delete what the flow has finished with.

    Takes the moment to prune at, defaulting to now. Returns a dict naming
    how many rows of each kind went. A spent or expired code is kept for an
    hour so that its reuse can still be recognised and answered by withdrawing
    what it produced; a withdrawn or expired token is kept a week so that the
    panel can still show what happened to it; a client that registered and was
    never approved is kept a day, which is longer than any real connector
    takes to complete the flow.
    """
    now = now or timezone.now()
    removed = {}

    removed["codes"] = AuthorizationCode.objects.filter(
        Q(expires_at__lt=now - SPENT_CODE_GRACE) | Q(used_at__lt=now - SPENT_CODE_GRACE)
    ).delete()[0]

    removed["refresh_tokens"] = RefreshToken.objects.filter(
        Q(expires_at__lt=now - DEAD_TOKEN_GRACE) | Q(revoked_at__lt=now - DEAD_TOKEN_GRACE)
    ).delete()[0]

    removed["access_tokens"] = AgentToken.objects.filter(
        issued_to__isnull=False
    ).filter(
        Q(expires_at__lt=now - DEAD_TOKEN_GRACE) | Q(revoked_at__lt=now - DEAD_TOKEN_GRACE)
    ).delete()[0]

    removed["clients"] = (
        OAuthClient.objects.filter(
            registered_dynamically=True,
            created_at__lt=now - UNUSED_CLIENT_GRACE,
            codes__isnull=True,
            refresh_tokens__isnull=True,
            access_tokens__isnull=True,
        )
        .delete()[0]
    )
    return removed
