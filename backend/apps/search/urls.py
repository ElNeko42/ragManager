"""Routes for the search endpoint and its record."""

from rest_framework.routers import SimpleRouter

from apps.search.views import SearchViewSet

router = SimpleRouter()
router.register("", SearchViewSet, basename="search")

urlpatterns = router.urls
