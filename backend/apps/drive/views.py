"""Management endpoints for collections, folders and documents."""

from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOwner
from apps.drive import services, storage
from apps.drive.models import Collection, Document, Folder
from apps.drive.serializers import (
    CollectionCreateSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    FolderCreateSerializer,
    FolderSerializer,
    FolderUpdateSerializer,
)


class CollectionListCreateView(APIView):
    """Lists the embedding models in use and registers new ones."""

    permission_classes = [IsOwner]

    def get(self, request):
        """Return every collection."""
        return Response(CollectionSerializer(Collection.objects.all(), many=True).data)

    def post(self, request):
        """Register a collection for one embedding model.

        Takes a name, a provider, a model name, a vector size and optionally
        the default flag. Returns the stored collection.
        """
        serializer = CollectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_default"):
                Collection.objects.filter(is_default=True).update(is_default=False)
            collection = serializer.save()
        return Response(CollectionSerializer(collection).data, status=status.HTTP_201_CREATED)


class CollectionDetailView(APIView):
    """Reads, retargets the default flag on, and removes a collection."""

    permission_classes = [IsOwner]

    def get(self, request, collection_id):
        """Return one collection."""
        return Response(CollectionSerializer(get_object_or_404(Collection, pk=collection_id)).data)

    def patch(self, request, collection_id):
        """Make this collection the default one, or stop it being so.

        Only the default flag can change: the name reaches Qdrant verbatim and
        the model and its dimension define the vectors already stored.
        """
        collection = get_object_or_404(Collection, pk=collection_id)
        serializer = CollectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data["is_default"]:
                Collection.objects.filter(is_default=True).update(is_default=False)
            collection.is_default = serializer.validated_data["is_default"]
            collection.save(update_fields=["is_default"])
        return Response(CollectionSerializer(collection).data)

    def delete(self, request, collection_id):
        """Remove a collection no folder points at.

        Returns 409 while folders still use it, because their documents were
        vectorised with that model.
        """
        collection = get_object_or_404(Collection, pk=collection_id)
        if collection.folders.exists():
            return Response(
                {"detail": "This collection is still used by folders"},
                status=status.HTTP_409_CONFLICT,
            )
        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FolderListCreateView(APIView):
    """Lists the folder tree and creates folders in it."""

    permission_classes = [IsOwner]

    def get(self, request):
        """Return every folder, flat, each naming its parent."""
        return Response(FolderSerializer(Folder.objects.all(), many=True).data)

    def post(self, request):
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


class FolderDetailView(APIView):
    """Reads, renames, moves and recursively deletes a folder."""

    permission_classes = [IsOwner]

    def get(self, request, folder_id):
        """Return one folder with its children and its documents."""
        folder = get_object_or_404(Folder, pk=folder_id)
        return Response(
            {
                "folder": FolderSerializer(folder).data,
                "children": FolderSerializer(folder.children.all(), many=True).data,
                "documents": DocumentSerializer(folder.documents.all(), many=True).data,
            }
        )

    def patch(self, request, folder_id):
        """Rename a folder, move it, or both."""
        folder = get_object_or_404(Folder, pk=folder_id)
        serializer = FolderUpdateSerializer(data=request.data, instance=folder)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(folder, field, value)
        folder.save()
        return Response(FolderSerializer(folder).data)

    def delete(self, request, folder_id):
        """Delete a folder, everything below it and every stored file.

        Returns 409 for the root folder, which is the anchor of the tree and
        of every permission lookup.
        """
        folder = get_object_or_404(Folder, pk=folder_id)
        if folder.parent_id is None:
            return Response(
                {"detail": "The root folder cannot be deleted"}, status=status.HTTP_409_CONFLICT
            )
        with transaction.atomic():
            services.delete_folder_tree(folder)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentListCreateView(APIView):
    """Lists documents and takes uploads into a folder."""

    permission_classes = [IsOwner]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        """Return documents, narrowed to one folder when it is given."""
        documents = Document.objects.all()
        folder_id = request.query_params.get("folder")
        if folder_id:
            documents = documents.filter(folder_id=folder_id)
        return Response(DocumentSerializer(documents, many=True).data)

    def post(self, request):
        """Upload a file into a folder.

        Takes the file, the destination folder and optionally a display name.
        The document is stored but nothing is queued: vectorising only starts
        when the agent flag is switched on. Returns the stored document.
        """
        upload_file = request.FILES.get("file")
        if upload_file is None:
            return Response({"file": "A file is required"}, status=status.HTTP_400_BAD_REQUEST)
        if upload_file.size > settings.MAX_UPLOAD_BYTES:
            return Response(
                {"file": f"The file exceeds the {settings.MAX_UPLOAD_BYTES} byte limit"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        folder = get_object_or_404(Folder, pk=request.data.get("folder"))
        name = request.data.get("name") or upload_file.name
        if Document.objects.filter(folder=folder, name=name).exists():
            return Response(
                {"name": "A document with this name already exists in that folder"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        document = services.create_document(folder, upload_file, name)
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    """Reads, renames, moves, toggles and deletes a document."""

    permission_classes = [IsOwner]

    def get(self, request, document_id):
        """Return one document."""
        return Response(DocumentSerializer(get_object_or_404(Document, pk=document_id)).data)

    def patch(self, request, document_id):
        """Rename a document, move it, or switch its agent flag.

        Switching the flag on queues the document for vectorising the first
        time; switching it off only hides its chunks from searches, so
        switching it back on makes them available again with no reprocessing.
        """
        document = get_object_or_404(Document, pk=document_id)
        serializer = DocumentUpdateSerializer(data=request.data, instance=document)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            document = services.update_document(document, serializer.validated_data)
        return Response(DocumentSerializer(document).data)

    def delete(self, request, document_id):
        """Delete a document and the file behind it."""
        with transaction.atomic():
            services.delete_document(get_object_or_404(Document, pk=document_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentContentView(APIView):
    """Serves and replaces the bytes of a document."""

    permission_classes = [IsOwner]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, document_id):
        """Stream the stored file back to the caller."""
        document = get_object_or_404(Document, pk=document_id)
        response = StreamingHttpResponse(
            storage.open_stream(document.storage_key).iter_chunks(),
            content_type=document.content_type,
        )
        response["Content-Disposition"] = f'attachment; filename="{document.name}"'
        response["Content-Length"] = document.size_bytes
        return response

    def put(self, request, document_id):
        """Replace the file behind a document.

        Takes the new file. Bumps the revision, drops the previous object and
        clears the processing state, since the chunks of the old revision no
        longer describe this file. Returns the updated document.
        """
        document = get_object_or_404(Document, pk=document_id)
        upload_file = request.FILES.get("file")
        if upload_file is None:
            return Response({"file": "A file is required"}, status=status.HTTP_400_BAD_REQUEST)
        if upload_file.size > settings.MAX_UPLOAD_BYTES:
            return Response(
                {"file": f"The file exceeds the {settings.MAX_UPLOAD_BYTES} byte limit"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        with transaction.atomic():
            document = services.replace_document(document, upload_file)
        return Response(DocumentSerializer(document).data)
