"""Routes for trying an embedding endpoint before a collection is saved."""

from rest_framework.routers import SimpleRouter

from apps.ingestion.views import ProviderViewSet

router = SimpleRouter()
router.register("", ProviderViewSet, basename="provider")

urlpatterns = router.urls
