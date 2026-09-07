"""Queueing and unwinding the vectorisation of documents."""

from django.db import transaction

from apps.drive.models import ProcessingStatus
from apps.ingestion import vectors
from apps.ingestion.models import ProcessingJob


def enqueue(document):
    """Queue a document for vectorising once the surrounding work commits.

    Takes the document. Creates the job row and hands the task to Celery only
    after the transaction commits, so the worker can never pick up a job whose
    document is not visible yet. Returns the job.
    """
    from apps.ingestion.tasks import process_document

    job = ProcessingJob.objects.create(document=document)
    document.processing_status = ProcessingStatus.PENDING
    document.save(update_fields=["processing_status", "updated_at"])
    transaction.on_commit(lambda: process_document.delay(str(job.pk)))
    return job


def discard_vectors(collection_name, document_id):
    """Drop every stored point of a document once the transaction commits.

    Takes the Qdrant collection name and the document id. Deferring to commit
    keeps a rolled back deletion from destroying vectors whose rows survived.
    """

    def cleanup():
        vectors.delete_document_points(collection_name, document_id)

    transaction.on_commit(cleanup)


def apply_payload(collection_name, document_id, values):
    """Push metadata changes onto the stored points after commit.

    Takes the Qdrant collection name, the document id and the fields to
    overwrite. Used for moves and for the agent flag, neither of which changes
    the text or the vectors, so nothing needs reprocessing.
    """

    def update():
        vectors.set_document_payload(collection_name, document_id, values)

    transaction.on_commit(update)
