"""Searching every collection an agent reaches and merging the results."""

from apps.access.resolver import resolve_access
from apps.drive.models import Collection, Document, Folder
from apps.drive.services import descendant_folders
from apps.ingestion import vectors
from apps.ingestion.embeddings import embed_texts

RANK_CONSTANT = 60
POOL_FACTOR = 2


def search(agent, query, limit, folder_id=None):
    """Find the chunks an agent may read that best answer a query.

    Takes the agent, the query text, how many chunks to return at most and the
    id of an optional folder to stay within, which includes everything below
    it. A folder that does not exist narrows the answer to nothing, the same as
    one the agent may not read. More chunks are fetched than asked for, because
    the database has the last word on which of them may be returned and a
    rejected one must not cost the caller a slot. Returns
    the chosen chunks, best first. The cost of the answer is set by this limit
    rather than by how many collections were consulted, so widening an agent's
    access does not widen what a model is later asked to read.
    """
    access = resolve_access(agent)
    if folder_id is not None:
        access = narrow_to_folder(access, Folder.objects.filter(pk=folder_id).first())
    if not access:
        return []
    collections = {
        collection.pk: collection
        for collection in Collection.objects.filter(pk__in=access.keys())
    }
    ranked = []
    for collection_id, scope in access.items():
        collection = collections[collection_id]
        hits = vectors.search(
            collection.name,
            embed_texts(collection, [query])[0],
            vectors.access_filter(scope["folders"], scope["documents"], scope["denied_documents"]),
            limit * POOL_FACTOR,
        )
        ranked.append([build_result(payload, score, collection) for payload, score in hits])
    pool = fuse(ranked, limit * POOL_FACTOR)
    return confirm_against_database(pool, access)[:limit]


def narrow_to_folder(access, folder):
    """Restrict an access map to one folder and everything under it.

    Takes the access map and the folder, which is None when the caller named
    one that does not exist. Either way the map narrows to nothing rather than
    raising, so an agent asking about a folder learns only that there is
    nothing there for it, and cannot tell a folder it may not read from one
    that was never created. Returns the narrowed map.
    """
    if folder is None:
        return {}
    subtree = {node.pk for node in descendant_folders(folder)}
    narrowed = {}
    for collection_id, scope in access.items():
        folders = [value for value in scope["folders"] if value in subtree]
        documents = [
            value
            for value in Document.objects.filter(
                pk__in=scope["documents"], folder__in=subtree
            ).values_list("document_id", flat=True)
        ]
        if folders or documents:
            narrowed[collection_id] = {
                "folders": folders,
                "documents": documents,
                "denied_documents": scope["denied_documents"],
            }
    return narrowed


def build_result(payload, score, collection):
    """Turn one Qdrant hit into the shape the callers of the search expect."""
    return {
        "document_id": payload["document_id"],
        "folder_id": payload["folder_id"],
        "chunk_index": payload["chunk_index"],
        "text": payload["text"],
        "score": score,
        "collection": collection.name,
    }


def fuse(ranked, limit):
    """Merge the results of several collections into one ordered list.

    Takes one ranked list per collection and how many results to keep. The
    merge is by position rather than by similarity, because a similarity from
    one embedding model says nothing about a similarity from another: the two
    numbers are not on the same scale and sorting their union would be
    arithmetic on incomparable quantities. Each result keeps the score its own
    collection gave it, for the caller to see. Returns the best results.
    """
    if len(ranked) == 1:
        return ranked[0][:limit]
    fused = {}
    for results in ranked:
        for position, result in enumerate(results):
            key = (result["document_id"], result["chunk_index"])
            entry = fused.setdefault(key, {"result": result, "rank_score": 0.0})
            entry["rank_score"] += 1.0 / (RANK_CONSTANT + position + 1)
    ordered = sorted(fused.values(), key=lambda entry: entry["rank_score"], reverse=True)
    return [entry["result"] for entry in ordered[:limit]]


def confirm_against_database(results, access):
    """Keep the results the database still agrees this agent may read.

    Takes the results and the access map they were searched under. The stored
    payload is what makes the search fast, but it is a copy: a document can be
    switched off, moved or deleted after its chunks were written, and if that
    change never reached the vector store the payload would still be inviting
    the agent in. So the three things that actually govern access are read back
    from the database here — the document exists, its switch is on, and it sits
    somewhere this agent reaches — and whatever fails any of them is dropped.
    Results also gain the name and the location their document holds now.
    Returns the confirmed results.
    """
    allowed_folders = set()
    allowed_documents = set()
    denied_documents = set()
    for scope in access.values():
        allowed_folders.update(str(value) for value in scope["folders"])
        allowed_documents.update(str(value) for value in scope["documents"])
        denied_documents.update(str(value) for value in scope["denied_documents"])

    rows = {
        str(document_id): (name, is_agent_active, str(folder_id))
        for document_id, name, is_agent_active, folder_id in Document.objects.filter(
            pk__in={result["document_id"] for result in results}
        ).values_list("document_id", "name", "is_agent_active", "folder_id")
    }
    confirmed = []
    for result in results:
        row = rows.get(result["document_id"])
        if row is None:
            continue
        name, is_active, folder_id = row
        if not is_active or result["document_id"] in denied_documents:
            continue
        if folder_id not in allowed_folders and result["document_id"] not in allowed_documents:
            continue
        result["document_name"] = name
        result["folder_id"] = folder_id
        confirmed.append(result)
    return confirmed
