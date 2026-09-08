"""Domain operations over the folder tree and its documents."""

import logging
import mimetypes
from pathlib import Path

from django.db import transaction

from apps.common import media_types
from apps.drive import storage
from apps.drive.models import Document, Folder, ProcessingStatus
from apps.ingestion import services as ingestion

logger = logging.getLogger(__name__)

KNOWN_SUFFIX_MEDIA_TYPES = {".docx": media_types.WORD}


def resolve_content_type(upload_file, name):
    """Work out the media type of an uploaded file.

    Takes the uploaded file and the name it will be stored under. Clients
    disagree about the type they send for office formats and many send the
    generic binary type, which would leave the pipeline unable to pick an
    extractor for a file it can perfectly well read, so an uninformative
    value is replaced by the one the extension implies. The office suffixes
    are listed here rather than left to the interpreter, whose table is
    populated from an operating system file that slim images do not ship.
    Returns the media type.
    """
    declared = upload_file.content_type or ""
    if declared and declared != media_types.GENERIC:
        return declared
    suffix = Path(name).suffix.lower()
    if suffix in KNOWN_SUFFIX_MEDIA_TYPES:
        return KNOWN_SUFFIX_MEDIA_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(name)
    return guessed or media_types.GENERIC


def descendant_folders(folder):
    """Collect a folder and every folder underneath it.

    Takes the folder to walk from. Returns a list ordered from the root of the
    subtree downwards, so reversing it yields the order in which folders can
    be deleted without tripping the protected foreign keys. Folders already
    seen are not followed again: a cycle written straight into the table would
    otherwise make this walk run forever.
    """
    collected = [folder]
    seen = {folder.pk}
    frontier = [folder]
    while frontier:
        children = [
            child
            for child in Folder.objects.filter(parent__in=frontier)
            if child.pk not in seen
        ]
        seen.update(child.pk for child in children)
        collected.extend(children)
        frontier = children
    return collected


def is_within(folder, candidate_parent):
    """Report whether a folder would end up inside its own subtree.

    Takes the folder being moved and the parent it would be moved under.
    Returns True when the move would create a cycle, and stops rather than
    looping when the stored tree already contains one.
    """
    node = candidate_parent
    seen = set()
    while node is not None and node.pk not in seen:
        if node.pk == folder.pk:
            return True
        seen.add(node.pk)
        node = node.parent
    return False


def create_document(folder, upload_file, name):
    """Store an uploaded file and register it in a folder.

    Takes the destination folder, the uploaded file and the display name.
    Returns the saved document, whose processing status stays null because
    nothing is queued until the agent flag is switched on. The caller runs
    this inside a transaction, so a storage failure leaves no row behind; the
    reverse, a stored object whose row never committed, wastes space but
    leaves nothing broken, which is the cheaper of the two failures.
    """
    document = Document.objects.create(
        folder=folder,
        name=name,
        content_type=resolve_content_type(upload_file, name),
        size_bytes=upload_file.size,
        storage_key="",
    )
    document.storage_key = storage.build_key(document.pk, document.revision, name)
    storage.upload(document.storage_key, upload_file, document.content_type)
    document.save(update_fields=["storage_key"])
    return document


def replace_document(document, upload_file):
    """Replace the contents of a document with a newly uploaded file.

    Takes the document and the uploaded file. Bumps the revision, writes the
    new object under a fresh key and removes the previous one. Resets the
    processing state, since the chunks of the old revision no longer describe
    this file. Returns the updated document.
    """
    previous_key = document.storage_key
    document.revision += 1
    document.content_type = resolve_content_type(upload_file, document.name)
    document.size_bytes = upload_file.size
    document.storage_key = storage.build_key(document.pk, document.revision, document.name)
    document.processing_status = None
    document.chunk_count = 0
    storage.upload(document.storage_key, upload_file, document.content_type)
    document.save(
        update_fields=[
            "revision",
            "content_type",
            "size_bytes",
            "storage_key",
            "processing_status",
            "chunk_count",
            "updated_at",
        ]
    )
    schedule_object_cleanup([previous_key])
    ingestion.discard_vectors(document.folder.collection.name, document.pk)
    if document.is_agent_active:
        ingestion.enqueue(document)
    return document


def delete_document(document):
    """Delete a document, the object backing it and its stored vectors."""
    key = document.storage_key
    collection_name = document.folder.collection.name
    document_id = document.pk
    document.delete()
    schedule_object_cleanup([key])
    ingestion.discard_vectors(collection_name, document_id)


def delete_folder_tree(folder):
    """Delete a folder, everything below it and every object it held.

    Takes the folder to remove. Deletes documents first and then the folders
    from the deepest upwards, because the foreign keys are protected on
    purpose so that nothing is ever removed by an implicit cascade.
    """
    folders = descendant_folders(folder)
    documents = Document.objects.filter(folder__in=folders).select_related("folder__collection")
    keys = []
    stored_vectors = []
    for document in documents:
        keys.append(document.storage_key)
        stored_vectors.append((document.folder.collection.name, document.pk))
    documents.delete()
    for node in reversed(folders):
        node.delete()
    schedule_object_cleanup(keys)
    for collection_name, document_id in stored_vectors:
        ingestion.discard_vectors(collection_name, document_id)


def schedule_object_cleanup(keys):
    """Remove stored objects once the surrounding transaction commits.

    Takes the keys to delete. Object storage cannot join the database
    transaction, so the deletion is deferred until the rows are truly gone: a
    rollback then leaves the files intact rather than losing them. A failure
    here leaves unreferenced objects behind, which wastes space but never
    loses data, so it is logged instead of raised.
    """
    keys = [key for key in keys if key]
    if not keys:
        return

    def cleanup():
        try:
            storage.delete(keys)
        except Exception:
            logger.exception("Could not delete %d object(s) from storage", len(keys))

    transaction.on_commit(cleanup)


def update_document(document, changes):
    """Apply a rename, a move or an agent flag switch, keeping Qdrant in step.

    Takes the document and the validated changes. A move inside the same
    collection only rewrites the folder on the stored points; a move into a
    folder using a different embedding model drops them and queues a fresh run,
    because vectors of different models are not interchangeable. Switching the
    flag off never deletes anything and switching it back on never reprocesses
    a document that is already indexed.

    An indexed document has its whole desired state pushed on every update
    rather than only the field that changed. Writing the difference meant that
    a push lost to an unreachable vector store could never be repeated: the row
    already held the new value, so the next attempt saw nothing to do and the
    stale payload stayed forever. Returns the updated document.
    """
    previous_collection = document.folder.collection
    was_active = document.is_agent_active
    for field, value in changes.items():
        setattr(document, field, value)
    document.save()
    document.refresh_from_db()
    collection = document.folder.collection

    if collection.pk != previous_collection.pk:
        ingestion.discard_vectors(previous_collection.name, document.pk)
        document.processing_status = None
        document.chunk_count = 0
        document.save(update_fields=["processing_status", "chunk_count", "updated_at"])
        if document.is_agent_active:
            ingestion.enqueue(document)
        return document

    if document.processing_status == ProcessingStatus.READY:
        ingestion.apply_payload(
            collection.name,
            document.pk,
            {
                "folder_id": str(document.folder_id),
                "is_agent_active": document.is_agent_active,
            },
        )
    elif document.is_agent_active and not was_active:
        ingestion.enqueue(document)
    return document
