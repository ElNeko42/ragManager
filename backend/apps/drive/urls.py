"""Routes for the document management API."""

from rest_framework.routers import SimpleRouter

from apps.drive.views import CollectionViewSet, DocumentViewSet, FolderViewSet

router = SimpleRouter()
router.register("collections", CollectionViewSet, basename="collection")
router.register("folders", FolderViewSet, basename="folder")
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = router.urls
