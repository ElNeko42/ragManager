"""Management command that puts a collection's embedding model to the test."""

import time

from django.core.management.base import BaseCommand, CommandError

from apps.drive.models import Collection, EmbeddingProvider
from apps.ingestion.embeddings import EmbeddingError, embed_texts, get_api_key
from apps.ingestion.failures import is_transient

PROBE_TEXTS = [
    "The quarterly figures were signed off by the finance team.",
    "El contrato se firmó en Valencia el pasado mes de marzo.",
]


class Command(BaseCommand):
    help = "Embed a couple of sentences with a collection's model and report what came back"

    def add_arguments(self, parser):
        """Declare the collection to test."""
        parser.add_argument("collection", help="The name of the registered collection")

    def handle(self, *args, **options):
        """Embed two sentences and report what the model answered.

        A collection is registered by typing an endpoint, a model name and a
        width into a form, and nothing checks any of it until a document is
        uploaded, switched on and put through the queue, where a wrong width or
        a rejected key surfaces as a failed job hours later. This asks the
        model directly, so the answer arrives while the form is still open.

        Raises CommandError when the model cannot be reached or disagrees with
        the collection, saying which of the two it was: an endpoint that timed
        out is worth trying again, a width that does not match never is.
        """
        try:
            collection = Collection.objects.get(name=options["collection"])
        except Collection.DoesNotExist:
            raise CommandError(f"No collection is registered under the name {options['collection']}")

        self.describe(collection)
        started = time.monotonic()
        try:
            vectors = embed_texts(collection, PROBE_TEXTS)
        except EmbeddingError as error:
            kind = "unreachable" if is_transient(error) else "misconfigured"
            raise CommandError(f"The model is {kind}: {error}")
        elapsed = int((time.monotonic() - started) * 1000)

        if len(vectors) != len(PROBE_TEXTS):
            raise CommandError(
                f"Asked for {len(PROBE_TEXTS)} vectors and received {len(vectors)}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(vectors)} vectors of {len(vectors[0])} dimensions in {elapsed} ms"
            )
        )
        words, overlap = collection.chunking_plan()
        self.stdout.write(f"Text is split into chunks of {words} words overlapping by {overlap}")

    def describe(self, collection):
        """Print where the vectors are about to come from.

        The endpoint and whether a credential was found are what a wrong answer
        usually turns out to be about, and neither is visible from the panel.
        """
        if collection.provider == EmbeddingProvider.LOCAL:
            self.stdout.write(f"Local model {collection.model_name}")
            return
        credential = "with a key" if get_api_key(collection) else "with no key"
        self.stdout.write(f"{collection.base_url} model {collection.model_name} {credential}")
