"""Endpoints that let the panel try an embedding endpoint before saving it."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOwner
from apps.drive.models import Collection
from apps.ingestion import providers
from apps.ingestion.embeddings import EmbeddingError, get_api_key
from apps.ingestion.serializers import ModelListSerializer, ProbeSerializer


class ProviderViewSet(viewsets.ViewSet):
    """Offers the known endpoints and asks one of them what it can do.

    Registering a collection means typing an endpoint, a model name and a
    width, and until now nothing checked any of the three until a document had
    been uploaded, switched on and put through the queue. These routes ask the
    endpoint itself while the form is still open.
    """

    permission_classes = [IsOwner]

    def list(self, request):
        """Return the endpoints offered as a starting point.

        Each carries a base URL to fill the form with and whether it wants a
        credential. Nothing here restricts what may be saved: an endpoint that
        is not on the list is typed in, which is the same field.
        """
        return Response({"providers": providers.catalogue()})

    @action(detail=False, methods=["post"], url_path="models", url_name="models")
    def models(self, request):
        """List the models one endpoint serves.

        Takes a base URL, optionally a credential, and optionally the
        collection whose stored credential to use instead, so that editing one
        does not mean typing its key again.

        Only the models that read like embedding models are offered. A provider
        usually serves a handful of them beside a long list of chat models, and
        one of those chosen by mistake registers a collection that can never
        index anything: the error surfaces once a document has been uploaded,
        switched on and put through the queue, far from the form that caused
        it. The reply says how many were left out, and everything can still be
        asked for.

        Returns 503 with what the endpoint said for a mistyped URL or a
        rejected key, since both are things to correct rather than errors in
        this server. An endpoint that serves one model and offers no list is
        answered with an empty list and a note saying so, not with a failure:
        most self-hosted ones are exactly that, and the form still works by
        typing the name and measuring it.
        """
        serializer = ModelListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            found = providers.list_models(
                serializer.validated_data["base_url"],
                self.credential(serializer.validated_data),
                providers.pattern_for(serializer.validated_data.get("provider")),
            )
        except providers.ModelListUnsupported as note:
            return Response(
                {
                    "models": [],
                    "listing_supported": False,
                    "filtered": False,
                    "hidden": 0,
                    "detail": str(note),
                }
            )
        except EmbeddingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.offer(found, serializer.validated_data.get("include_all")))

    def offer(self, found, include_all):
        """Decide which of the listed models to put in front of the owner.

        Takes the models and whether everything was asked for. Returns the
        answer the panel renders.

        Recognising an embedding model by its name is a guess, and a guess that
        matched nothing would leave a form with an empty list and no way
        forward, which is worse than the mistake it set out to prevent. So an
        empty result falls back to the whole list and says it did.
        """
        if include_all:
            return {"models": found, "listing_supported": True, "filtered": False, "hidden": 0}
        kept, hidden = providers.embedding_models(found)
        if not kept:
            return {
                "models": found,
                "listing_supported": True,
                "filtered": False,
                "hidden": 0,
                "detail": "None of these models is recognisable as an embedding model, "
                "so all of them are listed. Measuring one settles what it is.",
            }
        return {"models": kept, "listing_supported": True, "filtered": True, "hidden": hidden}

    @action(detail=False, methods=["post"], url_path="probe", url_name="probe")
    def probe(self, request):
        """Measure what one model actually answers with.

        Takes a base URL, a model and a credential the same three ways. Returns
        the width of the vector and the round trip. The width is measured here
        rather than typed into the form, because it is the one field an owner
        cannot know and the one that makes every stored vector unusable when it
        is wrong.
        """
        serializer = ProbeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            measured = providers.probe(
                serializer.validated_data["base_url"],
                self.credential(serializer.validated_data),
                serializer.validated_data["model_name"],
            )
        except EmbeddingError as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(measured)

    def credential(self, data):
        """Work out which credential to use for one call.

        Takes the validated request. A key typed into the form wins, because it
        is the one being tried; otherwise the collection named in the request
        lends the one it already holds, which is how a form reopened to change
        a model avoids asking for a key that is already stored.
        """
        if data.get("api_key"):
            return data["api_key"]
        collection_id = data.get("collection")
        if not collection_id:
            return None
        collection = Collection.objects.filter(pk=collection_id).first()
        return get_api_key(collection) if collection else None
