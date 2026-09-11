"""Turning text into vectors with the model a collection was created for."""

import os

import httpx
from django.conf import settings

from apps.common import secrets
from apps.drive.models import PASSAGE, EmbeddingProvider

API_TIMEOUT_SECONDS = 120
_loaded_models = {}


class EmbeddingError(Exception):
    """Raised when a collection's embedding model cannot produce vectors.

    The cause is kept attached, because the queue decides whether to try again
    by what actually went wrong: an endpoint that timed out is worth another
    attempt, a model whose width disagrees with the collection never is.
    """


def get_local_model(model_name):
    """Load a sentence-transformers model, reusing it across calls.

    Takes the model name. The import happens here rather than at module level
    so that a process which never embeds anything does not pay for loading
    torch. Returns the loaded model.
    """
    if model_name not in _loaded_models:
        from sentence_transformers import SentenceTransformer

        _loaded_models[model_name] = SentenceTransformer(model_name)
    return _loaded_models[model_name]


def reader_limits(collection):
    """Return how much of a chunk this collection's model will actually read.

    Takes the collection. Returns a (token budget, counter) pair, or a pair of
    Nones for a model this process cannot ask.

    A model reads so many tokens and ignores the rest without complaining, so
    a chunk longer than that is stored and returned in full while only its
    opening influenced the vector: the passage that answers the question is
    there and scores badly. How many words that is depends on the language as
    much as on the model, which is why it is measured rather than assumed. A
    model running in this process can be asked directly; one behind an
    endpoint cannot, and falls back to whatever the collection was told.
    """
    if collection.provider != EmbeddingProvider.LOCAL:
        return collection.max_tokens, None
    model = get_local_model(collection.model_name)
    budget = collection.max_tokens or model.max_seq_length
    tokenizer = model.tokenizer

    def count(text):
        """Return how many tokens this model spends on a piece of text."""
        return len(tokenizer.encode(text, add_special_tokens=False))

    return budget, count


def embed_texts(collection, texts, kind=PASSAGE):
    """Embed a list of texts with the model bound to a collection.

    Takes the collection record, the texts and whether they are passages being
    stored or a query being asked. Returns one vector per text in the same
    order. Raises EmbeddingError when the width the model returns disagrees
    with the one the collection was created with, which would make every
    stored vector unusable against the existing ones.

    A model that expects to be told which of the two it is reading gets that
    from the collection; one that does not carries no prefix and is asked
    exactly what it was asked before.
    """
    if not texts:
        return []
    texts = apply_prefix(collection, texts, kind)
    if collection.provider == EmbeddingProvider.LOCAL:
        vectors = embed_locally(collection.model_name, texts)
    else:
        vectors = embed_through_api(collection, texts)
    if len(vectors[0]) != collection.vector_size:
        raise EmbeddingError(
            f"The model returned {len(vectors[0])} dimensions but the collection "
            f"expects {collection.vector_size}"
        )
    return vectors


def apply_prefix(collection, texts, kind):
    """Put the words the model expects in front of each text.

    Takes the collection, the texts and whether they are a query or passages.
    Returns the texts unchanged when the collection names no prefix, which is
    every model that was never trained to be told the difference.
    """
    prefix = collection.prefix_for(kind)
    return [f"{prefix}{text}" for text in texts] if prefix else texts


def embed_locally(model_name, texts):
    """Embed texts with a model running inside this process.

    Takes the model name and the texts. Returns the vectors, normalised so
    that cosine distance behaves consistently against Qdrant.
    """
    model = get_local_model(model_name)
    return model.encode(texts, normalize_embeddings=True).tolist()


def get_api_key(collection):
    """Find the credential belonging to a collection's endpoint.

    Takes the collection. A credential stored through the panel wins, since it
    is the one somebody most recently said this collection should use. Failing
    that, a key named after the collection in the environment, and failing that
    the shared one: an instance holding collections at two different providers
    would otherwise send one provider's credential to the other, since the
    endpoint is chosen per collection but the shared key was not. Returns the
    key, or None when none is configured anywhere.

    A stored credential is encrypted in the row. It is still a row in a
    database somebody may be able to read, so an instance that would rather
    keep its secrets out of there can leave the field empty and use the
    environment exactly as before.
    """
    stored = secrets.decrypt(collection.encrypted_api_key)
    if stored:
        return stored
    suffix = collection.name.upper().replace("-", "_")
    return os.environ.get(f"EMBEDDING_API_KEY_{suffix}") or settings.EMBEDDING_API_KEY


def embed_through_api(collection, texts):
    """Embed texts through an OpenAI compatible embeddings endpoint.

    Takes the collection, which carries the endpoint and the model, and the
    texts. Any provider exposing that shape works unchanged, so the choice of
    company is configuration rather than code. Returns the vectors in request
    order. Raises EmbeddingError when the service answers with an error or a
    body that does not carry one vector per text.
    """
    headers = {"Content-Type": "application/json"}
    key = get_api_key(collection)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.post(
            f"{collection.base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"model": collection.model_name, "input": texts},
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()["data"]
    except httpx.HTTPError as error:
        raise EmbeddingError(f"The embeddings endpoint failed: {error}") from error
    except (KeyError, ValueError) as error:
        raise EmbeddingError(
            f"The embeddings endpoint returned an unexpected body: {error}"
        ) from error
    if len(payload) != len(texts):
        raise EmbeddingError(
            f"Asked for {len(texts)} embeddings and received {len(payload)}"
        )
    return [item["embedding"] for item in sorted(payload, key=lambda item: item.get("index", 0))]
