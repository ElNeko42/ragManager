"""Gateway to the S3 compatible object store."""

import boto3
from django.conf import settings
from django.utils.text import get_valid_filename

DELETE_BATCH_SIZE = 1000


def get_client():
    """Build a client bound to the configured object store."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
    )


def build_key(document_id, revision, name):
    """Compose the object key holding one revision of a document.

    Takes the document id, its revision number and the display name. The
    revision belongs in the key so that replacing a file never lets a cached
    copy of the previous one be served. Returns the key.
    """
    return f"documents/{document_id}/{revision}/{get_valid_filename(name)}"


def upload(key, fileobj, content_type):
    """Store a file under the given key, overwriting whatever was there."""
    get_client().upload_fileobj(
        fileobj, settings.S3_BUCKET, key, ExtraArgs={"ContentType": content_type}
    )


def open_stream(key):
    """Open a readable stream over a stored object.

    Returns the streaming body, which the caller is responsible for closing.
    """
    return get_client().get_object(Bucket=settings.S3_BUCKET, Key=key)["Body"]


def delete(keys):
    """Remove objects from the store.

    Takes an iterable of keys and deletes them in batches. Keys that are
    already gone are not an error, so a partially cleaned document can always
    be cleaned again.
    """
    keys = list(keys)
    if not keys:
        return
    client = get_client()
    for start in range(0, len(keys), DELETE_BATCH_SIZE):
        batch = keys[start : start + DELETE_BATCH_SIZE]
        client.delete_objects(
            Bucket=settings.S3_BUCKET,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )
