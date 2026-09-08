"""The endpoint an agent uses to search what it is allowed to read."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.agents.permissions import IsAgent
from apps.ingestion.embeddings import EmbeddingError
from apps.search import service
from apps.search.serializers import SearchSerializer


class SearchThrottle(UserRateThrottle):
    """Caps how often one agent may search.

    This is the only endpoint that costs something on every call: it embeds the
    query once per collection, which is either an inference on the web process
    or a billed request to a provider. A token that leaks would otherwise turn
    into an unbounded bill or a stalled server.
    """

    scope = "search"


class SearchView(APIView):
    """Answers a query with the chunks the calling agent may read."""

    permission_classes = [IsAgent]
    throttle_classes = [SearchThrottle]

    def post(self, request):
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
            )
        except EmbeddingError as error:
            return Response(
                {"detail": f"The embedding model is unavailable: {error}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"results": results})
