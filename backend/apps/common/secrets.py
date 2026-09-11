"""Encrypting the credentials that have to live in the database."""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class EncryptionUnavailable(Exception):
    """Raised when a credential is offered but nothing can encrypt it."""


def is_configured():
    """Report whether this instance can keep credentials at all."""
    return bool(settings.CREDENTIALS_ENCRYPTION_KEY)


def get_cipher():
    """Build the cipher from the key in the environment.

    The key is its own variable rather than the Django secret, because the
    Django secret is rotated to invalidate sessions and doing that must not
    quietly destroy every credential the panel holds. Raises
    EncryptionUnavailable when none is configured, which is what lets an
    instance run without ever storing a credential.
    """
    from cryptography.fernet import Fernet

    if not is_configured():
        raise EncryptionUnavailable(
            "Set CREDENTIALS_ENCRYPTION_KEY before storing a credential, or keep "
            "the key in the environment instead"
        )
    try:
        return Fernet(settings.CREDENTIALS_ENCRYPTION_KEY.encode("utf-8"))
    except (ValueError, TypeError) as error:
        raise EncryptionUnavailable(
            "CREDENTIALS_ENCRYPTION_KEY is not a valid key: generate one with "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from error


def encrypt(value):
    """Turn a credential into the text stored in its row.

    Takes the credential. Returns the encrypted text, or an empty string for
    an empty credential, which is how a stored key is cleared.
    """
    if not value:
        return ""
    return get_cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(stored):
    """Read a credential back out of its row.

    Takes the stored text. Returns the credential, or None when there is none
    and when the stored text cannot be read with the key this instance holds.
    A key that was rotated or lost therefore reads as no credential at all,
    which fails as a rejected request naming the endpoint rather than as an
    unhandled error on every ingestion run.
    """
    from cryptography.fernet import InvalidToken

    if not stored:
        return None
    try:
        return get_cipher().decrypt(stored.encode("ascii")).decode("utf-8")
    except EncryptionUnavailable:
        logger.error("A credential is stored but CREDENTIALS_ENCRYPTION_KEY is not set")
        return None
    except (InvalidToken, ValueError):
        logger.error("A stored credential cannot be read with the current encryption key")
        return None
