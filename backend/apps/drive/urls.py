"""Routes for the document management API."""

from django.urls import path

from apps.drive import views

urlpatterns = [
    path("collections/", views.CollectionListCreateView.as_view(), name="collection-list"),
    path(
        "collections/<uuid:collection_id>/",
        views.CollectionDetailView.as_view(),
        name="collection-detail",
    ),
    path("folders/", views.FolderListCreateView.as_view(), name="folder-list"),
    path("folders/<uuid:folder_id>/", views.FolderDetailView.as_view(), name="folder-detail"),
    path("documents/", views.DocumentListCreateView.as_view(), name="document-list"),
    path(
        "documents/<uuid:document_id>/", views.DocumentDetailView.as_view(), name="document-detail"
    ),
    path(
        "documents/<uuid:document_id>/content/",
        views.DocumentContentView.as_view(),
        name="document-content",
    ),
]
