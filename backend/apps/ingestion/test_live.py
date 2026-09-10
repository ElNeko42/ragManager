"""Contract tests that run against a real embeddings endpoint.

Everything else about the API provider is tested against a stub, which proves
the code does what this project believes the protocol to be and nothing about
whether that belief is right. These tests speak to a service that actually
implements it, so a provider answering in a shape this client cannot read is
found here rather than by a document that fails to index in production.

They are skipped unless an endpoint is named, because a test suite that needs
a network service is a test suite that fails for reasons that have nothing to
do with the change being made. To run them, point the variables at any
OpenAI compatible embeddings endpoint:

    LIVE_EMBEDDING_BASE_URL=http://localhost:8080/v1 \\
    LIVE_EMBEDDING_MODEL=<the model to ask for> \\
    LIVE_EMBEDDING_VECTOR_SIZE=<its width> \\
    LIVE_EMBEDDING_API_KEY=<a key, if the endpoint wants one> \\
    python manage.py test apps.ingestion.test_live

Any provider exposing that shape works, self-hosted or paid for: which company
runs the endpoint is configuration, not code, and these tests deliberately
name none.
"""

import os
import unittest

from django.test import TestCase

from apps.drive.models import Collection, EmbeddingProvider
from apps.ingestion.embeddings import EmbeddingError, embed_texts
from apps.ingestion.failures import is_transient

BASE_URL = os.environ.get("LIVE_EMBEDDING_BASE_URL")
MODEL = os.environ.get("LIVE_EMBEDDING_MODEL")
VECTOR_SIZE = os.environ.get("LIVE_EMBEDDING_VECTOR_SIZE")
API_KEY = os.environ.get("LIVE_EMBEDDING_API_KEY", "")

CONFIGURED = bool(BASE_URL and MODEL and VECTOR_SIZE)
REASON = "Set LIVE_EMBEDDING_BASE_URL, LIVE_EMBEDDING_MODEL and LIVE_EMBEDDING_VECTOR_SIZE"


@unittest.skipUnless(CONFIGURED, REASON)
class LiveEmbeddingTests(TestCase):
    """What a real provider has to do for this client to be right about it."""

    def setUp(self):
        """Register a collection pointing at the endpoint under test."""
        os.environ["EMBEDDING_API_KEY_LIVE_PROVIDER"] = API_KEY
        self.collection = Collection.objects.create(
            name="live-provider",
            provider=EmbeddingProvider.API,
            base_url=BASE_URL,
            model_name=MODEL,
            vector_size=int(VECTOR_SIZE),
        )

    def test_the_endpoint_answers_with_one_vector_per_text(self):
        """A short answer would silently pair chunks with the wrong vectors."""
        vectors = embed_texts(self.collection, ["first passage", "second passage"])
        self.assertEqual(len(vectors), 2)

    def test_the_vectors_are_the_width_the_collection_was_registered_with(self):
        """A width that disagrees makes every vector already stored unusable."""
        vectors = embed_texts(self.collection, ["a passage to embed"])
        self.assertEqual(len(vectors[0]), int(VECTOR_SIZE))

    def test_a_batch_keeps_the_order_it_was_sent_in(self):
        """Chunk three answering with chunk one's vector is undetectable later.

        The provider is free to answer out of order, marking each entry with
        its index, so this compares a batch against the same texts embedded one
        at a time: the two agree only if the order was restored correctly.
        """
        alone = [
            embed_texts(self.collection, ["the invoice was paid in March"])[0],
            embed_texts(self.collection, ["the roof was repaired in autumn"])[0],
        ]
        together = embed_texts(
            self.collection, ["the invoice was paid in March", "the roof was repaired in autumn"]
        )
        for one, batched in zip(alone, together):
            self.assertAlmostEqual(one[0], batched[0], places=4)
            self.assertAlmostEqual(one[-1], batched[-1], places=4)

    def test_the_same_text_always_embeds_to_the_same_vector(self):
        """A search only works if a stored chunk and a query are measured alike."""
        first = embed_texts(self.collection, ["a stable sentence"])[0]
        second = embed_texts(self.collection, ["a stable sentence"])[0]
        self.assertAlmostEqual(first[0], second[0], places=6)

    def test_texts_that_differ_embed_to_vectors_that_differ(self):
        """An endpoint answering with one constant vector would rank at random."""
        vectors = embed_texts(self.collection, ["snow in the mountains", "a mortgage contract"])
        self.assertNotAlmostEqual(vectors[0][0], vectors[1][0], places=6)

    def test_a_width_that_disagrees_is_refused_rather_than_stored(self):
        """Vectors of the wrong width poison the collection they are written to."""
        self.collection.vector_size = int(VECTOR_SIZE) + 1
        self.collection.save(update_fields=["vector_size"])
        with self.assertRaises(EmbeddingError):
            embed_texts(self.collection, ["a passage to embed"])

    def test_a_model_the_provider_does_not_serve_never_becomes_a_retry(self):
        """A name nobody serves is a form to correct, not a queue to retry.

        Whether it is refused at all is the provider's business: an endpoint
        serving one model ignores the name and answers with the model it has,
        which is how a collection can end up registered under a name nobody
        serves and still work. The width check is what catches that. What must
        not happen either way is the queue deciding this is worth trying again,
        since the name will be just as wrong on every later attempt.
        """
        self.collection.model_name = "a-model-that-does-not-exist-anywhere"
        self.collection.save(update_fields=["model_name"])
        try:
            vectors = embed_texts(self.collection, ["a passage to embed"])
        except EmbeddingError as error:
            self.assertFalse(is_transient(error))
        else:
            self.assertEqual(len(vectors[0]), int(VECTOR_SIZE))

    def test_an_endpoint_that_is_not_there_fails_as_something_to_retry(self):
        """A provider that is down comes back; the queue has to know that."""
        self.collection.base_url = "http://127.0.0.1:9/v1"
        self.collection.save(update_fields=["base_url"])
        with self.assertRaises(EmbeddingError) as raised:
            embed_texts(self.collection, ["a passage to embed"])
        self.assertTrue(is_transient(raised.exception))
