"""Telling a failure worth retrying apart from one that never will be."""

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

NETWORK_FAILURES = (
    httpx.TransportError,
    ResponseHandlingException,
    BotoCoreError,
    ConnectionError,
    TimeoutError,
)


class TransientFailure(Exception):
    """A dependency was unreachable, not a file this build cannot read."""


def is_transient(error):
    """Report whether an ingestion failure is worth trying again.

    Takes the exception. Returns True when it describes a dependency that was
    momentarily unavailable, which a later attempt can get past, and False for
    anything about the file itself: a format with no extractor, a model whose
    width disagrees with the collection, a name the store rejects. Retrying
    those spends the queue on work that will fail identically every time,
    while not retrying the first kind leaves a document failed forever because
    Qdrant was restarting for a minute.

    A cause is followed, so a failure wrapped in a message for the owner is
    still classified by what actually went wrong underneath.
    """
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, TransientFailure):
            return True
        if isinstance(error, NETWORK_FAILURES):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in RETRYABLE_STATUS_CODES
        if isinstance(error, UnexpectedResponse):
            return error.status_code in RETRYABLE_STATUS_CODES
        if isinstance(error, ClientError):
            return client_error_is_transient(error)
        error = error.__cause__ or error.__context__
    return False


def client_error_is_transient(error):
    """Report whether an object store refused for a reason that may pass.

    Takes the error the client raised. A throttled or unavailable store is
    worth asking again; a missing bucket or a rejected key is not, and would
    fail the same way on every attempt.
    """
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status in RETRYABLE_STATUS_CODES
