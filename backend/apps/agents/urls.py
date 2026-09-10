"""Routes for agent management and token issuing."""

from rest_framework.routers import SimpleRouter

from apps.agents.views import AgentViewSet

router = SimpleRouter()
router.register("", AgentViewSet, basename="agent")

urlpatterns = router.urls
