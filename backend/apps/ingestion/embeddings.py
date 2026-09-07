"""Turning text into vectors with the model a collection was created for."""

import os

import httpx
from django.conf import settings

from apps.drive.models import EmbeddingProvider

API_TIMEOUT_SECONDS = 120
_loaded_models = {}


class EmbeddingError(Exception):
    """Raised when a collection's embedding model cannot produce vectors."""


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


def embed_texts(collection, texts):
    """Embed a list of texts with the model bound to a collection.

    Takes the collection record and the texts. Returns one vector per text in
    the same order. Raises EmbeddingError when the width the model returns
    disagrees with the one the collection was created with, which would make
    every stored vector unusable against the existing ones.
    """
    if not texts:
        return []
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


def embed_locally(model_name, texts):
    """Embed texts with a model running inside this process.

    Takes the model name and the texts. Returns the vectors, normalised so
    that cosine distance behaves consistently against Qdrant.
    """
    model = get_local_model(model_name)
    return model.encode(texts, normalize_embeddings=True).tolist()


def get_api_key(collection):
    """Find the credential belonging to a collection's endpoint.

    Takes the collection and looks for a key named after it, falling back to
    the shared one. An instance holding collections at two different providers
    would otherwise send one provider's credential to the other, since the
    endpoint is chosen per collection but the key was not. The keys stay in the
    environment rather than in the row, because the row is readable from the
    database. Returns the key, or None when none is configured.
    """
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
        raise EmbeddingError(f"The embeddings endpoint failed: {error}")
    except (KeyError, ValueError) as error:
        raise EmbeddingError(f"The embeddings endpoint returned an unexpected body: {error}")
    if len(payload) != len(texts):
        raise EmbeddingError(
            f"Asked for {len(texts)} embeddings and received {len(payload)}"
        )
    return [item["embedding"] for item in sorted(payload, key=lambda item: item.get("index", 0))]
