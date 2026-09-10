"""Working out what one agent is allowed to search."""

from apps.access.models import Permission, PermissionEffect
from apps.drive.models import Document, Folder


def folder_rules(agent):
    """Read the rules one agent holds over folders.

    Takes the agent. Returns a dict of folder id to effect, which is small:
    an instance has one rule per folder the owner wrote one for, not one per
    folder that exists.
    """
    return dict(
        Permission.objects.filter(agent=agent, folder__isnull=False).values_list(
            "folder_id", "effect"
        )
    )


def resolve_folder_effects(agent, folders=None):
    """Compute the effective rule of every folder for one agent.

    Takes the agent and, when the caller has already read them, the folders as
    (id, parent id) pairs. Walks the tree downwards from the root: a folder carrying
    its own rule uses it, and one without inherits what its parent resolved to,
    so the nearest ancestor holding a rule is the one that decides. A folder
    the walk never reaches stays denied, which is what an agent with no rule
    anywhere on its path should get and also what a tree damaged into a cycle
    should resolve to. Returns a dict of folder id to effect.

    This reports on the whole tree, including everything the agent cannot
    reach, which is what the owner's panel needs and what an agent's own
    lookups must not pay for. Use reachable_folders for the latter.
    """
    if folders is None:
        folders = list(Folder.objects.values_list("folder_id", "parent_id"))
    rules = folder_rules(agent)
    effects = {folder_id: PermissionEffect.DENY for folder_id, _ in folders}
    children = {}
    root = None
    for folder_id, parent_id in folders:
        if parent_id is None:
            root = folder_id
        else:
            children.setdefault(parent_id, []).append(folder_id)
    if root is None:
        return effects

    visited = set()
    pending = [(root, PermissionEffect.DENY)]
    while pending:
        folder_id, inherited = pending.pop()
        if folder_id in visited:
            continue
        visited.add(folder_id)
        effect = rules.get(folder_id, inherited)
        effects[folder_id] = effect
        for child in children.get(folder_id, []):
            pending.append((child, effect))
    return effects


def reachable_folders(agent):
    """List the folders one agent may read, with the collection each sits in.

    Takes the agent. Returns a list of (folder id, collection id) pairs.

    The walk starts at the folders the agent was allowed outright and goes
    downwards one level per query, so the work grows with what the agent
    reaches rather than with how many folders the instance holds: an agent
    granted one folder costs the same whether the tree has ten folders or ten
    thousand. A folder carrying a rule of its own is never entered from above,
    because that rule is what decides it: a deny cuts the branch there, and an
    allow is already a starting point of its own. Folders already seen are not
    visited twice, so a tree damaged into a cycle ends the walk rather than
    running forever.
    """
    rules = folder_rules(agent)
    granted = [folder_id for folder_id, effect in rules.items() if effect == PermissionEffect.ALLOW]
    seen = set(rules)
    reached = list(Folder.objects.filter(pk__in=granted).values_list("folder_id", "collection_id"))
    frontier = [folder_id for folder_id, _ in reached]
    while frontier:
        rows = [
            row
            for row in Folder.objects.filter(parent__in=frontier).values_list(
                "folder_id", "collection_id"
            )
            if row[0] not in seen
        ]
        seen.update(folder_id for folder_id, _ in rows)
        reached.extend(rows)
        frontier = [folder_id for folder_id, _ in rows]
    return reached


def resolve_access(agent):
    """Group what an agent may search by the collection that holds it.

    Takes the agent. Returns a dict of collection id to the folder ids it may
    search there, the documents allowed in their own right, and the documents
    denied in their own right. A document rule always beats the folder it sits
    in, which is why the denied ones travel separately instead of being
    subtracted here: the search turns them into an exclusion on a filter that
    otherwise matches whole folders.
    """
    document_rules = Permission.objects.filter(agent=agent, document__isnull=False).values_list(
        "document_id", "effect"
    )
    document_collections = dict(
        Document.objects.filter(pk__in=[document_id for document_id, _ in document_rules])
        .values_list("document_id", "folder__collection_id")
    )

    access = {}
    for folder_id, collection_id in reachable_folders(agent):
        entry = access.setdefault(collection_id, empty_scope())
        entry["folders"].append(folder_id)
    for document_id, effect in document_rules:
        collection_id = document_collections.get(document_id)
        if collection_id is None:
            continue
        entry = access.setdefault(collection_id, empty_scope())
        key = "documents" if effect == PermissionEffect.ALLOW else "denied_documents"
        entry[key].append(document_id)
    return {
        collection_id: scope
        for collection_id, scope in access.items()
        if scope["folders"] or scope["documents"]
    }


def empty_scope():
    """Return the empty scope of one collection, ready to be filled in."""
    return {"folders": [], "documents": [], "denied_documents": []}
