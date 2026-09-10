"""The Celery task that turns a document into searchable vectors."""

import logging
import re
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.drive import storage
from apps.drive.models import ProcessingStatus
from apps.ingestion import chunking, extraction, vectors
from apps.ingestion.failures import is_transient
from apps.ingestion.models import ProcessingJob

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    soft_time_limit=settings.INGESTION_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.INGESTION_TIME_LIMIT_SECONDS,
)
def process_document(self, job_id):
    """Extract, chunk, embed and store one document.

    Takes the job id. Every run starts by deleting the points the document
    already had: identifiers are derived from the chunk position, so a shorter
    new revision would otherwise leave the surplus chunks of the previous one
    in place, answering searches with text the file no longer contains.

    A failure caused by a dependency being unreachable is queued again after a
    growing delay, because a vector store that was restarting for a minute
    would otherwise leave the document failed until somebody noticed. A
    failure caused by the file itself is recorded and not retried, since it
    would fail identically on every attempt and the queue is the wrong place
    to spend that. A run that overruns its budget is stopped and recorded the
    same way, so one unreadable scan cannot hold the only worker forever.
    """
    from apps.ingestion.embeddings import embed_texts

    job = ProcessingJob.objects.select_related("document__folder__collection").get(pk=job_id)
    document = job.document
    collection = document.folder.collection
    mark_running(job, document)
    try:
        data = storage.open_stream(document.storage_key).read()
        text = extraction.extract_text(data, document.content_type)
        chunks = chunking.split_text(text, *collection.chunking_plan())
        vectors.ensure_collection(collection)
        vectors.delete_document_points(collection.name, document.pk)
        if chunks:
            vectors.upsert_chunks(collection.name, document, chunks, embed_texts(collection, chunks))
        mark_succeeded(job, document, len(chunks))
    except Exception as error:
        if is_transient(error) and self.request.retries < settings.INGESTION_MAX_RETRIES:
            delay = retry_delay(self.request.retries)
            logger.warning(
                "Job %s could not reach a dependency, retrying in %ss: %s", job.pk, delay, error
            )
            mark_waiting(job, document, error, delay)
            raise self.retry(exc=error, countdown=delay)
        logger.exception("Job %s failed for document %s", job.pk, document.pk)
        mark_failed(job, document, error)
    return str(job.pk)


def retry_delay(retries):
    """Return how long to wait before the next attempt.

    Takes the number of attempts already made. The wait doubles each time so
    that a dependency coming back up is found quickly while one that stays
    down is not hammered, and it stops growing at the configured ceiling so a
    late attempt still happens within a working day.
    """
    return min(
        settings.INGESTION_RETRY_BACKOFF_SECONDS * (2**retries),
        settings.INGESTION_RETRY_MAX_BACKOFF_SECONDS,
    )


def mark_running(job, document):
    """Record that a job has started on both the job and its document."""
    job.status = ProcessingStatus.PROCESSING
    job.started_at = timezone.now()
    job.attempts += 1
    job.save(update_fields=["status", "started_at", "attempts"])
    document.processing_status = ProcessingStatus.PROCESSING
    document.save(update_fields=["processing_status", "updated_at"])


def mark_succeeded(job, document, chunk_count):
    """Record a finished job and the number of chunks it stored."""
    job.status = ProcessingStatus.READY
    job.finished_at = timezone.now()
    job.error_message = None
    job.save(update_fields=["status", "finished_at", "error_message"])
    document.processing_status = ProcessingStatus.READY
    document.chunk_count = chunk_count
    document.save(update_fields=["processing_status", "chunk_count", "updated_at"])


CREDENTIALS_IN_URL = re.compile(r"(?P<scheme>[a-zA-Z][\w+.-]*://)[^/\s@]*@")


def redact(text):
    """Remove the user and password a library may have echoed inside a URL.

    An exception raised by a storage or embedding client often repeats the
    endpoint it was given, credentials included. That text is stored on the job
    and shown to the owner, so the secret would end up in the database in plain
    text and in a browser. Returns the message with the credentials replaced.
    """
    return CREDENTIALS_IN_URL.sub(r"\g<scheme>***@", text)


def describe(error):
    """Return the sentence stored on a job to explain what went wrong."""
    return redact(f"{type(error).__name__}: {error}")


def mark_waiting(job, document, error, delay):
    """Record an attempt that will be made again after a delay.

    Takes the job, its document, the failure and the wait before the next
    attempt. The document goes back to pending rather than to failed, because
    it is still on its way: showing it as failed would tell the owner to act
    on something the queue is already handling. The reason is kept so that a
    document sitting in the queue for a while can be explained without reading
    the worker's log.
    """
    job.status = ProcessingStatus.PENDING
    job.error_message = describe(error)
    job.next_attempt_at = timezone.now() + timedelta(seconds=delay)
    job.save(update_fields=["status", "error_message", "next_attempt_at"])
    document.processing_status = ProcessingStatus.PENDING
    document.save(update_fields=["processing_status", "updated_at"])


def mark_failed(job, document, error):
    """Record a failed job and the reason it gave."""
    job.status = ProcessingStatus.FAILED
    job.finished_at = timezone.now()
    job.error_message = describe(error)
    job.next_attempt_at = None
    job.save(update_fields=["status", "finished_at", "error_message", "next_attempt_at"])
    document.processing_status = ProcessingStatus.FAILED
    document.save(update_fields=["processing_status", "updated_at"])
