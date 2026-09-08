"""Gateway to Qdrant, where the chunk text and its vector live."""

import uuid

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

POINT_NAMESPACE = uuid.UUID("6f1d5a7e-8c3b-4f2a-9d61-2b7e4c0a8f35")


def get_client():
    """Build a client bound to the configured Qdrant instance."""
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)


def build_point_id(document_id, chunk_index):
    """Derive the identifier of one chunk inside Qdrant.

    Takes the document id and the position of the chunk. The identifier is
    derived rather than stored, which is why Postgres keeps no chunk table:
    the same document and position always resolve to the same point, so a
    reprocess overwrites in place instead of duplicating.
    """
    return str(uuid.uuid5(POINT_NAMESPACE, f"{document_id}:{chunk_index}"))


def ensure_collection(collection):
    """Create the Qdrant collection backing a model, if it is not there yet.

    Takes the collection record, whose vector size and name were fixed when it
    was registered and cannot change afterwards.
    """
    client = get_client()
    if client.collection_exists(collection.name):
        return
    client.create_collection(
        collection_name=collection.name,
        vectors_config=qmodels.VectorParams(
            size=collection.vector_size, distance=qmodels.Distance.COSINE
        ),
    )
    for field in ("document_id", "folder_id", "is_agent_active"):
        client.create_payload_index(
            collection_name=collection.name,
            field_name=field,
            field_schema=qmodels.PayloadSchemaType.KEYWORD
            if field != "is_agent_active"
            else qmodels.PayloadSchemaType.BOOL,
        )


def delete_document_points(collection_name, document_id):
    """Remove every point belonging to a document.

    Takes the Qdrant collection name and the document id. This runs before any
    reprocess: point identifiers are derived from the chunk position, so a
    shorter new revision would otherwise leave the surplus chunks of the old
    one behind, still answering searches with text the file no longer holds.
    """
    client = get_client()
    if not client.collection_exists(collection_name):
        return
    client.delete(
        collection_name=collection_name,
        points_selector=qmodels.FilterSelector(filter=document_filter(document_id)),
        wait=True,
    )


def document_filter(document_id):
    """Build the Qdrant filter that matches every point of one document."""
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="document_id", match=qmodels.MatchValue(value=str(document_id))
            )
        ]
    )


def upsert_chunks(collection_name, document, chunks, vectors):
    """Write the chunks of a document with their vectors and metadata.

    Takes the collection name, the document, its chunk texts and the matching
    vectors. The payload carries the chunk text, which lives here and nowhere
    else, plus the fields the search filters on. Permissions are deliberately
    absent: they are resolved in Postgres and turned into a filter at query
    time, so granting access never has to rewrite stored points.
    """
    points = [
        qmodels.PointStruct(
            id=build_point_id(document.pk, index),
            vector=vector,
            payload={
                "document_id": str(document.pk),
                "folder_id": str(document.folder_id),
                "is_agent_active": document.is_agent_active,
                "chunk_index": index,
                "text": chunk,
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    get_client().upsert(collection_name=collection_name, points=points, wait=True)


def set_document_payload(collection_name, document_id, values):
    """Update payload fields on every point of a document.

    Takes the collection name, the document id and the fields to overwrite.
    Used when a document is moved or its agent flag is switched, neither of
    which changes the text or the vectors.
    """
    client = get_client()
    if not client.collection_exists(collection_name):
        return
    client.set_payload(
        collection_name=collection_name,
        payload=values,
        points=qmodels.FilterSelector(filter=document_filter(document_id)).filter,
        wait=True,
    )


def count_document_points(collection_name, document_id):
    """Return how many points a document currently holds in Qdrant."""
    client = get_client()
    if not client.collection_exists(collection_name):
        return 0
    return client.count(
        collection_name=collection_name, count_filter=document_filter(document_id), exact=True
    ).count


def access_filter(folders, documents, denied_documents):
    """Build the Qdrant filter that expresses what an agent may see.

    Takes the folder ids an agent may search, the documents allowed in their
    own right and the documents denied in their own right. The two allow lists
    are combined as a nested alternative rather than as loose optional clauses,
    so the meaning is unambiguous: the chunk must be active, must belong either
    to a permitted folder or to a permitted document, and must not belong to a
    denied one. Returns the filter.

    Raises ValueError when nothing at all is allowed. A filter built from two
    empty lists would carry no restriction and match every active chunk in the
    collection, so the one input that must never produce a filter is the one
    that describes an agent permitted nothing.
    """
    if not folders and not documents:
        raise ValueError(
            "Refusing to build an access filter with nothing allowed: an empty scope "
            "must be answered without searching, never by searching without limits"
        )
    alternatives = []
    if folders:
        alternatives.append(
            qmodels.FieldCondition(
                key="folder_id", match=qmodels.MatchAny(any=[str(value) for value in folders])
            )
        )
    if documents:
        alternatives.append(
            qmodels.FieldCondition(
                key="document_id", match=qmodels.MatchAny(any=[str(value) for value in documents])
            )
        )
    must = [
        qmodels.FieldCondition(key="is_agent_active", match=qmodels.MatchValue(value=True)),
        qmodels.Filter(should=alternatives),
    ]
    must_not = []
    if denied_documents:
        must_not.append(
            qmodels.FieldCondition(
                key="document_id",
                match=qmodels.MatchAny(any=[str(value) for value in denied_documents]),
            )
        )
    return qmodels.Filter(must=must, must_not=must_not)


def search(collection_name, vector, query_filter, limit):
    """Return the closest chunks of one collection that pass a filter.

    Takes the collection name, the query vector, the filter and how many hits
    to return. Returns a list of (payload, score) pairs, closest first, or
    nothing when the collection has never been written to.
    """
    client = get_client()
    if not client.collection_exists(collection_name):
        return []
    hits = client.query_points(
        collection_name=collection_name,
        query=vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    ).points
    return [(hit.payload, hit.score) for hit in hits]
