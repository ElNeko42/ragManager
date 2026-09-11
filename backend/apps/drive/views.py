"""Management endpoints for collections, folders and documents."""

from django.db import transaction
from django.http import FileResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOwner
from apps.drive import services, storage
from apps.drive.models import Collection, Document, Folder
from apps.drive.serializers import (
    CollectionCreateSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
    DocumentDetailSerializer,
    DocumentFilterSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    DocumentUploadSerializer,
    FolderCreateSerializer,
    FolderSerializer,
    FolderUpdateSerializer,
)

UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


class OwnerViewSet(viewsets.GenericViewSet):
    """What every management endpoint shares.

    The identifiers of this API are all uuids, and the route only matches one:
    a malformed id is then a route that does not exist, which answers 404,
    rather than a value that reaches the query layer and surfaces as a 500.
    """

    permission_classes = [IsOwner]
    lookup_value_regex = UUID_PATTERN


class CollectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    OwnerViewSet,
):
    """Lists the embedding models in use, registers and retires them."""

    queryset = Collection.objects.all()
    lookup_field = "collection_id"
    serializer_class = CollectionSerializer

    def get_serializer_class(self):
        """Pick the serializer that matches what this call is allowed to change."""
        if self.action == "create":
            return CollectionCreateSerializer
        return CollectionSerializer

    def create(self, request, *args, **kwargs):
        """Register a collection for one embedding model.

        Takes a name, a provider, a model name, a vector size, optionally the
        chunk size its text is split with and optionally the default flag.
        Returns the stored collection.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_default"):
                Collection.objects.filter(is_default=True).update(is_default=False)
            collection = serializer.save()
        return Response(CollectionSerializer(collection).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Change the default flag or the chunk size of a collection.

        The name reaches Qdrant verbatim and the model and its dimension define
        the vectors already stored, so neither can move. The chunk size can:
        it only decides how the next document is split, and re-indexing what is
        already there is a separate deliberate step.
        """
        collection = self.get_object()
        serializer = CollectionUpdateSerializer(
            data=request.data, instance=collection, partial=True
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_default"):
                Collection.objects.filter(is_default=True).update(is_default=False)
            collection = serializer.save()
        return Response(CollectionSerializer(collection).data)

    def destroy(self, request, *args, **kwargs):
        """Remove a collection no folder points at.

        Returns 409 while folders still use it, because their documents were
        vectorised with that model.
        """
        collection = self.get_object()
        if collection.folders.exists():
            return Response(
                {"detail": "This collection is still used by folders"},
                status=status.HTTP_409_CONFLICT,
            )
        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FolderViewSet(mixins.ListModelMixin, OwnerViewSet):
    """Lists the folder tree, creates folders and moves them about."""

    queryset = Folder.objects.all()
    lookup_field = "folder_id"
    serializer_class = FolderSerializer

    def create(self, request, *args, **kwargs):
        """Create a folder under an existing one.

        Takes a name, a parent and optionally a collection, which otherwise is
        inherited from the parent. The collection cannot change afterwards,
        since it fixes the embedding model of everything stored inside.
        """
        serializer = FolderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = serializer.validated_data["parent"]
        folder = Folder.objects.create(
            name=serializer.validated_data["name"],
            parent=parent,
            collection=serializer.validated_data.get("collection", parent.collection),
        )
        return Response(FolderSerializer(folder).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        """Return one folder with its children and its documents.

        The documents are paged like the listing is, since a folder can hold
        as many of them as the whole instance can.
        """
        folder = self.get_object()
        page = self.paginate_queryset(folder.documents.all())
        return Response(
            {
                "folder": FolderSerializer(folder).data,
                "children": FolderSerializer(folder.children.all(), many=True).data,
                "documents": self.paginator.get_paginated_response(
                    DocumentSerializer(page, many=True).data
                ).data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        """Rename a folder, move it, change the root's model, or all three.

        Changing the model is only offered on the root, where it is the model
        this instance uses by default. Whatever sat directly in the root was
        vectorised with the old one, so it is queued again under the new one.
        """
        folder = self.get_object()
        serializer = FolderUpdateSerializer(data=request.data, instance=folder)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        collection = changes.pop("collection", None)
        with transaction.atomic():
            for field, value in changes.items():
                setattr(folder, field, value)
            folder.save()
            if collection is not None:
                folder = services.change_folder_collection(folder, collection)
        return Response(FolderSerializer(folder).data)

    def destroy(self, request, *args, **kwargs):
        """Delete a folder, everything below it and every stored file.

        Returns 409 for the root folder, which is the anchor of the tree and
        of every permission lookup.
        """
        folder = self.get_object()
        if folder.parent_id is None:
            return Response(
                {"detail": "The root folder cannot be deleted"}, status=status.HTTP_409_CONFLICT
            )
        with transaction.atomic():
            services.delete_folder_tree(folder)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentViewSet(mixins.ListModelMixin, OwnerViewSet):
    """Lists documents, takes uploads and serves the bytes back.

    The parsers are left as they come. An upload arrives as multipart and
    everything else as JSON, and the framework picks by what the request
    declares: naming only the multipart ones here, as the upload view used to
    when it was a view of its own, refuses a JSON body on every other route of
    the set, which is most of them.
    """

    queryset = Document.objects.all()
    lookup_field = "document_id"
    serializer_class = DocumentSerializer

    def get_queryset(self):
        """Return the documents asked for, narrowed to one folder when given."""
        documents = Document.objects.all()
        filters = DocumentFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        folder = filters.validated_data.get("folder")
        if folder is not None:
            documents = documents.filter(folder_id=folder)
        return documents

    def create(self, request, *args, **kwargs):
        """Upload a file into a folder.

        Takes the file, the destination folder and optionally a display name.
        The whole thing runs in one transaction, so a storage failure leaves no
        row behind holding a name nobody can reuse. The document is stored but
        nothing is queued: vectorising only starts when the agent flag is
        switched on. Returns the stored document.
        """
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload_file = serializer.validated_data["file"]
        with transaction.atomic():
            document = services.create_document(
                serializer.validated_data["folder"],
                upload_file,
                serializer.validated_data.get("name") or upload_file.name,
            )
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        """Return one document, with the reason its last run failed."""
        return Response(DocumentDetailSerializer(self.get_object()).data)

    def partial_update(self, request, *args, **kwargs):
        """Rename a document, move it, or switch its agent flag.

        Switching the flag on queues the document for vectorising the first
        time; switching it off only hides its chunks from searches, so
        switching it back on makes them available again with no reprocessing.
        """
        document = self.get_object()
        serializer = DocumentUpdateSerializer(data=request.data, instance=document)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            document = services.update_document(document, serializer.validated_data)
        return Response(DocumentSerializer(document).data)

    def destroy(self, request, *args, **kwargs):
        """Delete a document and the file behind it."""
        with transaction.atomic():
            services.delete_document(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reprocess", url_name="reprocess")
    def reprocess(self, request, *args, **kwargs):
        """Put a document back in the queue.

        The queue retries a dependency that was unreachable on its own, but a
        run that failed for good, or one whose file was only ever half read,
        needs somebody to say so. Returns 409 for a document no agent may read,
        since vectorising it would index something nothing is allowed to
        search. Returns the document with its new pending state.
        """
        document = self.get_object()
        if not document.is_agent_active:
            return Response(
                {"detail": "Switch the document on for agents before queueing it"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            document = services.reprocess_document(document)
        return Response(DocumentSerializer(document).data)

    @action(detail=True, methods=["get", "put"], url_path="content", url_name="content")
    def content(self, request, *args, **kwargs):
        """Serve or replace the bytes of a document."""
        if request.method == "PUT":
            return self.replace_content(request)
        return self.read_content()

    def read_content(self):
        """Stream the stored file back to the caller.

        The response is built by the framework so that a name carrying quotes
        or characters outside ASCII is encoded as the header format requires
        instead of breaking it, and so that the declared length is the one it
        actually sends rather than a stored figure that could disagree.
        """
        document = self.get_object()
        return FileResponse(
            storage.open_stream(document.storage_key),
            as_attachment=True,
            filename=document.name,
            content_type=document.content_type,
        )

    def replace_content(self, request):
        """Replace the file behind a document.

        Takes the new file. Bumps the revision, drops the previous object and
        clears the processing state, since the chunks of the old revision no
        longer describe this file. Oversized bodies are refused before they
        reach here. Returns the updated document.
        """
        document = self.get_object()
        upload_file = request.FILES.get("file")
        if upload_file is None:
            return Response({"file": "A file is required"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            document = services.replace_document(document, upload_file)
        return Response(DocumentSerializer(document).data)
