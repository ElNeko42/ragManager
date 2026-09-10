"""The endpoint an agent uses to search, and the record it leaves behind."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.accounts.permissions import IsOwner
from apps.agents.permissions import IsAgent
from apps.ingestion.embeddings import EmbeddingError
from apps.search import service
from apps.search.models import AgentQuery, QuerySource
from apps.search.serializers import (
    AgentQuerySerializer,
    QueryLogFilterSerializer,
    SearchSerializer,
)


class SearchThrottle(UserRateThrottle):
    """Caps how often one agent may search.

    This is the only endpoint that costs something on every call: it embeds the
    query once per collection, which is either an inference on the web process
    or a billed request to a provider. A token that leaks would otherwise turn
    into an unbounded bill or a stalled server.
    """

    scope = "search"


class SearchViewSet(viewsets.GenericViewSet):
    """Answers a query with the chunks the calling agent may read."""

    permission_classes = [IsAgent]
    serializer_class = SearchSerializer

    def get_throttles(self):
        """Meter the searching, not the owner reading the log of it."""
        return [] if self.action == "log" else [SearchThrottle()]

    def get_permissions(self):
        """Give each route to whoever it belongs to.

        Searching is an agent's, and the record of what agents searched for is
        the owner's: an agent that could read the log would learn what every
        other agent was asked to look into.
        """
        return [IsOwner()] if self.action == "log" else [IsAgent()]

    def create(self, request):
        """Search everything the calling agent reaches.

        Takes a query, optionally how many chunks to return and a folder to
        stay within, which includes everything below it. The agent never names
        a collection or a permission: which collections were consulted and
        which rules applied is decided here from its token. Returns the chosen
        chunks, best first, or 503 when the embedding model cannot be reached,
        so that an automated caller can tell a broken dependency from a bad
        request and retry accordingly.
        """
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            results = service.search(
                request.user,
                serializer.validated_data["query"],
                serializer.validated_data["limit"],
                folder_id=serializer.validated_data.get("folder"),
                source=QuerySource.API,
            )
        except EmbeddingError as error:
            return Response(
                {"detail": f"The embedding model is unavailable: {error}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"results": results})

    @action(detail=False, methods=["get"], url_path="log", url_name="log")
    def log(self, request):
        """Return what agents have searched for, most recent first.

        Takes an optional agent to narrow to. The client of this store is an
        agent rather than a person, so its questions are the only account of
        what it went looking for and whether it found anything: a run of
        answers with nothing in them usually means a permission is missing
        rather than that the store is empty.
        """
        filters = QueryLogFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queries = AgentQuery.objects.all()
        agent = filters.validated_data.get("agent")
        if agent is not None:
            queries = queries.filter(agent_id=agent)
        page = self.paginate_queryset(queries)
        return self.get_paginated_response(AgentQuerySerializer(page, many=True).data)
