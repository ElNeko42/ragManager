"""Turning text into vectors with the model a collection was created for."""

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
        vectors = embed_through_api(collection.base_url, collection.model_name, texts)
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


def embed_through_api(base_url, model_name, texts):
    """Embed texts through an OpenAI compatible embeddings endpoint.

    Takes the base URL of the service, the model name and the texts. Any
    provider exposing that shape works unchanged, so the choice of company is
    configuration rather than code. Returns the vectors in request order.
    Raises EmbeddingError when the service answers with an error or a body
    that does not carry one vector per text.
    """
    headers = {"Content-Type": "application/json"}
    if settings.EMBEDDING_API_KEY:
        headers["Authorization"] = f"Bearer {settings.EMBEDDING_API_KEY}"
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"model": model_name, "input": texts},
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
