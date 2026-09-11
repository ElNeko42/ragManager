"""The endpoints offered in the panel, and what one of them can be asked."""

import json
import re
import time

import httpx
from django.conf import settings

from apps.ingestion.embeddings import API_TIMEOUT_SECONDS, EmbeddingError

LIST_TIMEOUT_SECONDS = 20
NO_LISTING_STATUS_CODES = frozenset({404, 405, 501})
PROBE_TEXT = "A short sentence used to measure the width of a model."
EMBEDDING_HINTS = (
    "embed",
    "bge",
    "e5",
    "gte",
    "minilm",
    "nomic",
    "mxbai",
    "arctic",
    "stella",
    "voyage",
)

# A reranker scores a pair of texts and returns no vector at all. Several
# providers list theirs beside their embedding models, and its name often
# carries the same words, so it is ruled out wherever it appears.
NEVER_EMBEDDING = re.compile(r"rerank", re.IGNORECASE)


class ModelListUnsupported(Exception):
    """Raised by an endpoint that embeds but offers no list of its models.

    A server dedicated to one model has nothing to list and answers the
    listing route with a refusal. That is not a fault to report: the model
    name is simply typed in and measured, which settles it either way.
    """


def catalogue():
    """Read the list of endpoints offered as a starting point.

    Returns the providers as plain dictionaries. The list is a file rather
    than a table of vendors in the code: this project knows about an endpoint
    shape, and which company serves it is configuration. An operator may point
    PROVIDER_CATALOGUE at their own file, and a broken one leaves the panel
    with the custom endpoint it always has rather than failing to load.
    """
    try:
        with open(settings.PROVIDER_CATALOGUE, encoding="utf-8") as handle:
            return json.load(handle).get("providers", [])
    except (OSError, ValueError):
        return []


def headers(api_key):
    """Build the request headers for an endpoint, with a key when there is one."""
    built = {"Content-Type": "application/json"}
    if api_key:
        built["Authorization"] = f"Bearer {api_key}"
    return built


def list_models(base_url, api_key, pattern=None):
    """Ask an endpoint which models it serves.

    Takes the base URL, the credential and the pattern this provider names its
    embedding models with. Returns the model identifiers it reports, each
    marked with whether it reads like an embedding model.

    Raises ModelListUnsupported for an endpoint that serves one model and has
    no list to give, which is most self-hosted ones and is not a fault. Raises
    EmbeddingError when the endpoint cannot be reached, refuses the credential
    or answers with something that is not a model list, which is how a
    mistyped URL or a rejected key is found before anything is saved.
    """
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/models",
            headers=headers(api_key),
            timeout=LIST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()["data"]
    except httpx.HTTPStatusError as error:
        if error.response.status_code in NO_LISTING_STATUS_CODES:
            raise ModelListUnsupported(
                "This endpoint does not list its models; type the model name instead"
            ) from error
        raise EmbeddingError(f"The endpoint refused the request: {error}") from error
    except httpx.HTTPError as error:
        raise EmbeddingError(f"The endpoint could not be reached: {error}") from error
    except (KeyError, TypeError, ValueError) as error:
        raise EmbeddingError(
            f"The endpoint did not answer with a list of models: {error}"
        ) from error
    return [
        {"id": name, "looks_like_embedding": looks_like_embedding(name, pattern)}
        for name in sorted(str(item.get("id", "")) for item in payload if item.get("id"))
    ]


def embedding_models(models):
    """Keep the models that read like embedding models.

    Takes the models as listed. Returns the ones to offer and how many were
    left out, so that the panel can say what it is not showing.

    A provider serving three embedding models beside two hundred chat models
    is the normal case, and a chat model chosen from that list registers a
    collection that can never index anything: the mistake is only found when a
    document has been uploaded, switched on and put through the queue. Hiding
    them is worth it. Hiding all of them would not be, which is why the caller
    is told the count and can still ask for everything.
    """
    kept = [model for model in models if model["looks_like_embedding"]]
    return kept, len(models) - len(kept)


def looks_like_embedding(name, pattern=None):
    """Report whether a model name reads like an embedding model.

    Takes the identifier and, when the provider is known, the pattern its
    catalogue entry gives for naming embedding models. Falls back to a generic
    guess for an endpoint nobody has described, which is every custom one.

    This is a guess about a name, not a fact about a model: nothing in the
    answer an endpoint gives says what a model does, and the only way to know
    is to ask it to embed something. So it decides what a list shows first and
    what it hides behind a second click, never what may be registered.
    """
    if NEVER_EMBEDDING.search(name):
        return False
    if pattern:
        try:
            return bool(re.search(pattern, name, re.IGNORECASE))
        except re.error:
            return False
    lowered = name.lower()
    return any(hint in lowered for hint in EMBEDDING_HINTS)


def pattern_for(provider_id):
    """Return the naming pattern one catalogued provider uses, if it has one.

    Takes the provider identifier the panel sent. Returns None for an endpoint
    that is not in the catalogue, which then falls back to the generic guess.
    """
    for provider in catalogue():
        if provider.get("id") == provider_id:
            return provider.get("embedding_pattern")
    return None


def probe(base_url, api_key, model):
    """Embed one sentence and report what the model answered with.

    Takes the base URL, the credential and the model. Returns the width of the
    vector and how long the round trip took. The width is measured rather than
    typed in, because it is the one field an owner cannot guess and the one
    that makes every stored vector unusable when it is wrong.
    """
    started = time.monotonic()
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=headers(api_key),
            json={"model": model, "input": [PROBE_TEXT]},
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
    except httpx.HTTPError as error:
        raise EmbeddingError(f"The endpoint could not be reached: {error}") from error
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise EmbeddingError(f"The endpoint answered with an unexpected body: {error}") from error
    return {"vector_size": len(vector), "duration_ms": int((time.monotonic() - started) * 1000)}
