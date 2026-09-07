"""The vectorisation queue."""

import uuid

from django.db import models

from apps.drive.models import Document, ProcessingStatus


class ProcessingJob(models.Model):
    """One ingestion attempt for one document.

    A row is kept per attempt so that a failure and its error survive the next
    retry. The document caches the status of its latest job.
    """

    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="jobs")
    status = models.CharField(
        max_length=16, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "processing_jobs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document", "-created_at"], name="processing_jobs_document_idx")
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=ProcessingStatus.values),
                name="processing_jobs_status_in_choices",
            )
        ]

    def __str__(self):
        """Return the document name and the job status."""
        return f"{self.document.name} [{self.status}]"
