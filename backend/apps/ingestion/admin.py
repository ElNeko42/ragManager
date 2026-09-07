"""Admin registration for the vectorisation queue."""

from django.contrib import admin

from apps.ingestion.models import ProcessingJob


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ("document", "status", "created_at", "started_at", "finished_at")
    list_filter = ("status",)
    readonly_fields = ("job_id", "created_at", "started_at", "finished_at")
