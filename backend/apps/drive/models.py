"""Collections, the folder tree and the documents stored in it."""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class EmbeddingProvider(models.TextChoices):
    """Where the embeddings of a collection are computed.

    Deliberately free of vendor names: anything reachable over an OpenAI
    compatible endpoint is the same provider as far as this project cares, and
    which company runs it is a matter of configuration, not of code.
    """

    LOCAL = "local", "Local model"
    API = "api", "API endpoint"


class ProcessingStatus(models.TextChoices):
    """Lifecycle of an ingestion run."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class Collection(models.Model):
    """A Qdrant collection, one per embedding model.

    Vectors of different models cannot share a collection, so the model and its
    dimension are fixed here and every folder points at the collection whose
    model it uses.
    """

    collection_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=63,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9][a-z0-9_-]*$",
                message="Use lowercase letters, digits, hyphens and underscores",
            )
        ],
    )
    provider = models.CharField(max_length=16, choices=EmbeddingProvider.choices)
    base_url = models.URLField(max_length=500, blank=True, default="")
    model_name = models.CharField(max_length=200)
    vector_size = models.PositiveIntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "collections"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="collections_single_default",
            ),
            models.CheckConstraint(
                condition=models.Q(provider__in=EmbeddingProvider.values),
                name="collections_provider_in_choices",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(provider=EmbeddingProvider.LOCAL)
                    | ~models.Q(base_url="")
                ),
                name="collections_api_requires_base_url",
            ),
        ]

    def __str__(self):
        """Return the collection name."""
        return self.name


class Folder(models.Model):
    """A node of the folder tree.

    Exactly one row has no parent: the root folder created at installation, so
    that every document and every permission lookup walks a complete path.
    """

    folder_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    name = models.CharField(max_length=255)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="folders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "folders"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"], name="folders_unique_name_per_parent"
            ),
            models.UniqueConstraint(
                fields=["parent"],
                condition=models.Q(parent__isnull=True),
                nulls_distinct=False,
                name="folders_only_one_root",
            ),
        ]

    def __str__(self):
        """Return the folder name."""
        return self.name

    def clean(self):
        """Reject a parent that would put this folder inside its own subtree.

        A cycle cannot be expressed as a database constraint, and once written
        it makes every walk of the tree run forever, so the check lives here
        where the admin and any form both pass through it.
        """
        node = self.parent
        seen = set()
        while node is not None and node.pk not in seen:
            if node.pk == self.pk:
                raise ValidationError({"parent": "A folder cannot be placed inside itself"})
            seen.add(node.pk)
            node = node.parent


class Document(models.Model):
    """A file stored in object storage and optionally exposed to agents.

    A null processing status means the file has been uploaded but never
    activated, so nothing has ever been queued for it.
    """

    document_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(Folder, on_delete=models.PROTECT, related_name="documents")
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150)
    size_bytes = models.PositiveBigIntegerField()
    storage_key = models.CharField(max_length=1024)
    revision = models.PositiveIntegerField(default=1)
    processing_status = models.CharField(
        max_length=16, choices=ProcessingStatus.choices, null=True, blank=True
    )
    is_agent_active = models.BooleanField(default=False)
    chunk_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "documents"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["folder", "name"], name="documents_unique_name_per_folder"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(processing_status__in=ProcessingStatus.values)
                    | models.Q(processing_status__isnull=True)
                ),
                name="documents_status_in_choices",
            ),
        ]
        indexes = [models.Index(fields=["is_agent_active"], name="documents_agent_active_idx")]

    def __str__(self):
        """Return the document name."""
        return self.name
