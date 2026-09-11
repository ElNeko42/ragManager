"""Tests for splitting text, for classifying failures and for the queue."""

from unittest.mock import patch

import httpx
from botocore.exceptions import ClientError
from celery.exceptions import Retry
from django.test import TestCase, override_settings
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from apps.drive.models import PASSAGE, QUERY, Collection, Document, Folder, ProcessingStatus
from apps.ingestion import chunking, tasks
from apps.ingestion.embeddings import EmbeddingError, embed_texts
from apps.ingestion.extraction import ExtractionError
from apps.ingestion.failures import TransientFailure, is_transient
from apps.ingestion.models import ProcessingJob


class ChunkSizeTests(TestCase):
    """The size of a chunk, which decides what the model actually reads."""

    def test_text_with_no_words_produces_no_chunks(self):
        """An empty extraction must not write a point carrying nothing."""
        self.assertEqual(chunking.split_text("   \n\n  ", 200, 40), [])

    def test_a_smaller_size_produces_more_chunks_from_the_same_text(self):
        """A file that yields two chunks is two chances for a search to match."""
        text = " ".join(f"word{index}" for index in range(1000))
        self.assertGreater(len(chunking.split_text(text, 100, 20)), len(chunking.split_text(text, 400, 60)))

    def test_no_chunk_is_much_longer_than_the_size_asked_for(self):
        """Everything past what the model reads is stored but never embedded."""
        text = ". ".join("word " * 30 for _ in range(40))
        for chunk in chunking.split_text(text, 200, 40):
            self.assertLessEqual(len(chunk.split()), 260)

    def test_an_overlap_as_long_as_the_chunk_is_refused(self):
        """Repeating every chunk whole would double the store for nothing."""
        with self.assertRaises(ValueError):
            chunking.split_text("a b c", 100, 100)

    def test_chunks_repeat_the_words_the_overlap_asks_for(self):
        """An idea cut in half by a boundary has to survive whole somewhere."""
        text = ". ".join(f"sentence{index} filler filler filler filler" for index in range(60))
        chunks = chunking.split_text(text, 100, 25)
        self.assertTrue(set(chunks[0].split()) & set(chunks[1].split()))

    def test_a_chunk_ends_where_a_sentence_does(self):
        """A chunk that begins mid sentence embeds as a fragment and scores low."""
        text = ". ".join(f"sentence number {index} carries on for a while" for index in range(40))
        for chunk in chunking.split_text(text, 60, 15)[:-1]:
            self.assertTrue(chunk.endswith(".") or chunk.split()[-1].isalnum())

    def test_a_sentence_longer_than_a_chunk_is_still_cut(self):
        """Recognised text arrives with no punctuation to break it at."""
        chunks = chunking.split_text(" ".join(["word"] * 900), 200, 40)
        self.assertTrue(all(len(chunk.split()) <= 200 for chunk in chunks))

    def test_splitting_always_ends(self):
        """A step that never advances would spin forever inside a worker."""
        self.assertLess(len(chunking.split_text(" ".join(["w"] * 500), 30, 29)), 100)


class ChunkingPlanTests(TestCase):
    """Where the size of a chunk is read from."""

    def setUp(self):
        """Take the collection the instance was installed with."""
        self.collection = Collection.objects.get(is_default=True)

    @override_settings(CHUNK_WORDS=250, CHUNK_OVERLAP_WORDS=50)
    def test_a_collection_naming_no_size_follows_the_instance(self):
        """One place to change it is what makes the default worth having."""
        self.assertEqual(self.collection.chunking_plan(), (250, 50))

    @override_settings(CHUNK_WORDS=250, CHUNK_OVERLAP_WORDS=50)
    def test_a_collection_may_name_its_own_size(self):
        """Every model reads a different amount, so the size belongs to it."""
        self.collection.chunk_words = 120
        self.collection.chunk_overlap_words = 30
        self.assertEqual(self.collection.chunking_plan(), (120, 30))

    @override_settings(CHUNK_WORDS=250, CHUNK_OVERLAP_WORDS=50)
    def test_an_overlap_of_zero_is_kept_rather_than_replaced(self):
        """Asking for no overlap at all is a choice, not a missing value."""
        self.collection.chunk_overlap_words = 0
        self.assertEqual(self.collection.chunking_plan()[1], 0)


class FailureClassificationTests(TestCase):
    """Which failures are worth queueing again and which never will be."""

    def response(self, status_code):
        """Build an HTTP failure carrying one status code."""
        request = httpx.Request("POST", "http://example.invalid")
        answer = httpx.Response(status_code, request=request)
        return httpx.HTTPStatusError("failed", request=request, response=answer)

    def test_a_vector_store_that_cannot_be_reached_is_transient(self):
        """Qdrant restarting for a minute must not fail a document for good."""
        self.assertTrue(is_transient(ResponseHandlingException(OSError("refused"))))

    def test_a_vector_store_answering_with_an_outage_is_transient(self):
        """A 503 is the store saying to come back, not that the file is bad."""
        self.assertTrue(is_transient(UnexpectedResponse(503, "unavailable", b"", None)))

    def test_a_vector_store_refusing_the_request_is_permanent(self):
        """A request the store will never accept fails the same way every time."""
        self.assertFalse(is_transient(UnexpectedResponse(400, "bad request", b"", None)))

    def test_an_object_store_that_is_throttling_is_transient(self):
        """Being asked to slow down is not a reason to give up on a file."""
        error = ClientError({"ResponseMetadata": {"HTTPStatusCode": 503}}, "GetObject")
        self.assertTrue(is_transient(error))

    def test_an_object_store_refusing_the_key_is_permanent(self):
        """A rejected credential is a setting to correct, not a queue to spin."""
        error = ClientError({"ResponseMetadata": {"HTTPStatusCode": 403}}, "GetObject")
        self.assertFalse(is_transient(error))

    def test_an_embedding_endpoint_that_timed_out_is_transient(self):
        """A provider having a bad minute must not cost the document its index."""
        try:
            raise httpx.ConnectTimeout("timed out")
        except httpx.ConnectTimeout as cause:
            error = EmbeddingError("The embeddings endpoint failed") 
            error.__cause__ = cause
        self.assertTrue(is_transient(error))

    def test_a_width_that_disagrees_is_permanent(self):
        """A model returning the wrong width will return it again forever."""
        self.assertFalse(is_transient(EmbeddingError("returned 768 dimensions")))

    def test_a_file_with_no_extractor_is_permanent(self):
        """Trying again cannot teach this build to read a format it has not got."""
        self.assertFalse(is_transient(ExtractionError("no extractor")))

    def test_a_failure_declared_transient_is_believed(self):
        """Code that knows a dependency was down has to be able to say so."""
        self.assertTrue(is_transient(TransientFailure("the store was restarting")))

    def test_an_overloaded_endpoint_is_transient(self):
        """A 429 means later, and later is exactly what a retry is."""
        self.assertTrue(is_transient(self.response(429)))

    def test_a_rejected_credential_is_permanent(self):
        """A key the provider refuses is refused on every attempt."""
        self.assertFalse(is_transient(self.response(401)))


@override_settings(
    INGESTION_MAX_RETRIES=3,
    INGESTION_RETRY_BACKOFF_SECONDS=10,
    INGESTION_RETRY_MAX_BACKOFF_SECONDS=100,
)
class QueueRetryTests(TestCase):
    """What the queue does with a run that could not finish."""

    def setUp(self):
        """Register a document with a job waiting to be run."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.document = Document.objects.create(
            folder=self.root,
            name="report.txt",
            content_type="text/plain",
            size_bytes=10,
            storage_key="documents/report.txt",
            is_agent_active=True,
        )
        self.job = ProcessingJob.objects.create(document=self.document)

    def run_task(self, error, retries=0):
        """Run one attempt of the task with the storage read failing.

        Takes the failure and how many attempts have already been made. Only
        one attempt is run: letting the queue re-enter the task here would test
        the loop rather than what one attempt decides. Returns whether the
        attempt asked to be queued again.
        """
        task = tasks.process_document
        task.push_request(retries=retries)
        retried = False
        try:
            with (
                patch("apps.drive.storage.open_stream", side_effect=error),
                patch.object(task, "retry", side_effect=Retry("later")),
            ):
                try:
                    task.run(str(self.job.pk))
                except Retry:
                    retried = True
        finally:
            task.pop_request()
        self.job.refresh_from_db()
        self.document.refresh_from_db()
        return retried

    def test_a_dependency_that_was_down_is_queued_again(self):
        """Qdrant restarting for a minute must not cost a document its index."""
        self.assertTrue(self.run_task(TransientFailure("the store was restarting")))

    def test_a_dependency_that_was_down_leaves_the_document_pending(self):
        """Failed is what the owner acts on, and there is nothing to act on yet."""
        self.run_task(TransientFailure("the store was restarting"))
        self.assertEqual(self.document.processing_status, ProcessingStatus.PENDING)

    def test_a_dependency_that_was_down_records_why_it_is_waiting(self):
        """A document sitting in the queue has to be explainable without the log."""
        self.run_task(TransientFailure("the store was restarting"))
        self.assertIn("restarting", self.job.error_message)

    def test_a_dependency_that_was_down_names_when_it_will_be_tried_again(self):
        """A queue with no visible next attempt looks identical to a stuck one."""
        self.run_task(TransientFailure("down"))
        self.assertIsNotNone(self.job.next_attempt_at)

    def test_a_file_that_cannot_be_read_fails_at_once(self):
        """Retrying a format with no extractor spends the queue on nothing."""
        self.assertFalse(self.run_task(ExtractionError("no extractor for this type")))
        self.assertEqual(self.document.processing_status, ProcessingStatus.FAILED)

    def test_a_dependency_still_down_after_every_attempt_finally_fails(self):
        """A queue that never gives up hides an outage that lasted all day."""
        self.assertFalse(self.run_task(TransientFailure("still down"), retries=3))
        self.assertEqual(self.document.processing_status, ProcessingStatus.FAILED)

    def test_every_attempt_is_counted_on_the_same_job(self):
        """Three jobs saying nothing is worse than one saying it took three goes."""
        self.run_task(TransientFailure("down"))
        self.run_task(TransientFailure("down"), retries=1)
        self.assertEqual(self.job.attempts, 2)

    def test_the_wait_grows_with_each_attempt(self):
        """Asking a dependency that is down every ten seconds helps nobody."""
        self.assertLess(tasks.retry_delay(0), tasks.retry_delay(2))

    def test_the_wait_stops_growing_at_the_ceiling(self):
        """A late attempt still has to happen within a working day."""
        self.assertEqual(tasks.retry_delay(20), 100)

    def test_a_credential_inside_a_url_never_reaches_the_stored_reason(self):
        """The reason is shown in a browser, so a secret must not travel in it."""
        self.run_task(ExtractionError("failed at https://user:secret@store.example/bucket"))
        self.assertNotIn("secret", self.job.error_message)


class PrefixTests(TestCase):
    """The words a model expects in front of what it is asked to read."""

    def setUp(self):
        """Take a collection and give it the prefixes of the e5 family."""
        self.collection = Collection.objects.get(is_default=True)
        self.collection.query_prefix = "query: "
        self.collection.passage_prefix = "passage: "

    def embed(self, texts, kind):
        """Embed through the local path with the model itself stubbed out."""
        with patch("apps.ingestion.embeddings.embed_locally") as locally:
            locally.return_value = [[0.0] * self.collection.vector_size for _ in texts]
            embed_texts(self.collection, texts, kind=kind)
        return locally.call_args.args[1]

    def test_a_passage_is_sent_with_the_passage_prefix(self):
        """A model trained on the prefix reads a bare passage as something else."""
        self.assertEqual(self.embed(["the invoice"], PASSAGE), ["passage: the invoice"])

    def test_a_query_is_sent_with_the_query_prefix(self):
        """Measuring a question as though it were an answer costs accuracy quietly."""
        self.assertEqual(self.embed(["where is it"], QUERY), ["query: where is it"])

    def test_a_collection_naming_no_prefix_sends_the_text_unchanged(self):
        """Most models were never trained to be told which kind they are reading."""
        self.collection.query_prefix = ""
        self.collection.passage_prefix = ""
        self.assertEqual(self.embed(["plain text"], QUERY), ["plain text"])

    def test_passages_are_what_a_caller_gets_without_saying(self):
        """Ingestion is the busiest caller, so the safe default is its own."""
        self.assertEqual(
            self.embed(["stored text"], PASSAGE), self.embed(["stored text"], "passage")
        )

    def test_every_text_of_a_batch_carries_the_prefix(self):
        """One unprefixed chunk in a batch is one chunk measured differently."""
        self.assertEqual(
            self.embed(["one", "two"], PASSAGE), ["passage: one", "passage: two"]
        )


class TokenBudgetTests(TestCase):
    """Keeping a chunk inside what the model will actually read."""

    def count(self, text):
        """Stand in for a tokeniser that spends two tokens on every word."""
        return len(text.split()) * 2

    def test_no_chunk_passes_the_budget(self):
        """Everything past it is stored and returned but never embedded."""
        text = ". ".join("palabra " * 20 for _ in range(40))
        for chunk in chunking.split_text(text, 500, 50, max_tokens=100, count_tokens=self.count):
            self.assertLessEqual(self.count(chunk), 100)

    def test_the_budget_closes_a_chunk_before_the_word_target_does(self):
        """A word count is a guess at the budget; the budget is the real limit."""
        text = ". ".join("palabra " * 20 for _ in range(40))
        loose = chunking.split_text(text, 500, 50)
        tight = chunking.split_text(text, 500, 50, max_tokens=100, count_tokens=self.count)
        self.assertGreater(len(tight), len(loose))

    def test_a_sentence_costing_more_than_the_budget_is_cut(self):
        """Otherwise it becomes one chunk that no model reads to the end."""
        text = " ".join(["palabra"] * 400)
        for chunk in chunking.split_text(text, 500, 50, max_tokens=100, count_tokens=self.count):
            self.assertLessEqual(self.count(chunk), 100)

    def test_the_ratio_is_taken_from_the_text_rather_than_assumed(self):
        """Spanish costs a model trained on English far more tokens per word."""
        text = " ".join(["palabra"] * 200)
        expensive = chunking.split_text(
            text, 500, 0, max_tokens=100, count_tokens=lambda t: len(t.split()) * 5
        )
        cheap = chunking.split_text(
            text, 500, 0, max_tokens=100, count_tokens=lambda t: len(t.split())
        )
        self.assertGreater(len(expensive), len(cheap))

    def test_without_a_counter_nothing_changes(self):
        """A model behind an endpoint cannot be asked, and must still work."""
        text = ". ".join("palabra " * 20 for _ in range(10))
        self.assertTrue(chunking.split_text(text, 100, 20))


class StructureTests(TestCase):
    """What a chunk keeps of the way the document was written."""

    def test_line_breaks_survive(self):
        """A price list flattened into one line is a price list nobody can read."""
        text = "Planes\n\nSTART: 189 euros.\nPLUS: 270 euros.\nPROFESSIONAL: 460 euros."
        self.assertIn("\n", chunking.split_text(text, 100, 20)[0])

    def test_a_chunk_is_cut_from_the_document_rather_than_rebuilt(self):
        """Rebuilding it from words loses every list, heading and table."""
        text = "Titulo\n\n- uno\n- dos\n- tres"
        self.assertIn("- uno\n- dos", chunking.split_text(text, 100, 20)[0])

    def test_the_overlap_stays_near_what_was_asked_for(self):
        """Every word repeated is a word the reader pays for twice."""
        text = ". ".join(f"frase numero {index} con su relleno correspondiente" for index in range(60))
        chunks = chunking.split_text(text, 60, 10)
        for first, second in zip(chunks, chunks[1:]):
            words = first.split()
            repeated = next(
                (k for k in range(min(len(words), len(second.split())), 0, -1)
                 if words[-k:] == second.split()[:k]),
                0,
            )
            self.assertLessEqual(repeated, 20)
