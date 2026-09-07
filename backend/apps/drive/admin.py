"""Admin registration for collections, folders and documents."""

from django.contrib import admin

from apps.drive.models import Collection, Document, Folder


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "model_name", "vector_size", "is_default")
    readonly_fields = ("collection_id", "created_at")


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "collection", "created_at")
    list_filter = ("collection",)
    readonly_fields = ("folder_id", "created_at", "updated_at")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "folder",
        "content_type",
        "size_bytes",
        "revision",
        "processing_status",
        "is_agent_active",
        "chunk_count",
    )
    list_filter = ("processing_status", "is_agent_active", "folder")
    readonly_fields = ("document_id", "created_at", "updated_at")
