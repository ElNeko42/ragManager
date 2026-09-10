"""Routes for the agent access rules."""

from rest_framework.routers import SimpleRouter

from apps.access.views import PermissionViewSet

router = SimpleRouter()
router.register("", PermissionViewSet, basename="permission")

urlpatterns = router.urls
