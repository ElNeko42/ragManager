"""The vectorisation queue."""

import uuid

from django.db import models

from apps.drive.models import Document, ProcessingStatus


class ProcessingJob(models.Model):
    """One ingestion run for one document.

    A row is kept per run, and a run that was queued again after an
    unreachable dependency counts its attempts on the same row, so a document
    that took three tries to index leaves one job saying so rather than three
    jobs saying nothing. The document caches the status of its latest job.
    """

    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="jobs")
    status = models.CharField(
        max_length=16, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
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
