"""Minting and hashing of the short lived secrets the flow passes around."""

import hashlib
import secrets

from django.views.decorators.debug import sensitive_variables

CODE_BYTES = 32
SECRET_BYTES = 32
REFRESH_PREFIX = "rmr_"


@sensitive_variables()
def mint(prefix=""):
    """Mint a secret with enough entropy that guessing is not a strategy."""
    return f"{prefix}{secrets.token_urlsafe(CODE_BYTES)}"


@sensitive_variables()
def digest(value):
    """Hash a secret for storage and lookup.

    SHA-256 rather than a slow password hash, for the same reason the agent
    tokens use it: the value carries 256 bits of entropy, so stretching buys
    nothing against guessing while forbidding the indexed lookup every request
    depends on.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@sensitive_variables()
def verify(value, stored):
    """Compare a secret against its stored hash without leaking the answer.

    The comparison takes the same time whether it fails on the first byte or
    the last, so the time it took says nothing about how close a guess was.
    """
    if not stored:
        return False
    return secrets.compare_digest(digest(value), stored)


@sensitive_variables()
def verify_challenge(verifier, challenge):
    """Check a PKCE verifier against the challenge sent with the request.

    Takes the verifier the client kept and the challenge it published when it
    started. Only S256 is accepted: the plain method proves nothing an
    attacker holding the authorization request could not also produce.
    """
    if not verifier or not challenge:
        return False
    import base64

    computed = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return secrets.compare_digest(computed.rstrip(b"=").decode("ascii"), challenge)
