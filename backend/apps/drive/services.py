"""Domain operations over the folder tree and its documents."""

import logging

from django.db import transaction

from apps.drive import storage
from apps.drive.models import Document, Folder

logger = logging.getLogger(__name__)


def get_root_folder():
    """Return the root folder created at installation."""
    return Folder.objects.get(parent__isnull=True)


def descendant_folders(folder):
    """Collect a folder and every folder underneath it.

    Takes the folder to walk from. Returns a list ordered from the root of the
    subtree downwards, so reversing it yields the order in which folders can
    be deleted without tripping the protected foreign keys.
    """
    collected = [folder]
    frontier = [folder]
    while frontier:
        children = list(Folder.objects.filter(parent__in=frontier))
        collected.extend(children)
        frontier = children
    return collected


def is_within(folder, candidate_parent):
    """Report whether a folder would end up inside its own subtree.

    Takes the folder being moved and the parent it would be moved under.
    Returns True when the move would create a cycle.
    """
    node = candidate_parent
    while node is not None:
        if node.pk == folder.pk:
            return True
        node = node.parent
    return False


def create_document(folder, upload_file, name):
    """Store an uploaded file and register it in a folder.

    Takes the destination folder, the uploaded file and the display name.
    Returns the saved document, whose processing status stays null because
    nothing is queued until the agent flag is switched on.
    """
    document = Document.objects.create(
        folder=folder,
        name=name,
        content_type=upload_file.content_type or "application/octet-stream",
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
    document.content_type = upload_file.content_type or "application/octet-stream"
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
    return document


def delete_document(document):
    """Delete a document and the object backing it."""
    key = document.storage_key
    document.delete()
    schedule_object_cleanup([key])


def delete_folder_tree(folder):
    """Delete a folder, everything below it and every object it held.

    Takes the folder to remove. Deletes documents first and then the folders
    from the deepest upwards, because the foreign keys are protected on
    purpose so that nothing is ever removed by an implicit cascade.
    """
    folders = descendant_folders(folder)
    documents = Document.objects.filter(folder__in=folders)
    keys = list(documents.values_list("storage_key", flat=True))
    documents.delete()
    for node in reversed(folders):
        node.delete()
    schedule_object_cleanup(keys)


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
