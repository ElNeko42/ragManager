"""The tools an external agent may call, and what each one does.

Every tool is a thin wrapper over work the HTTP API already does, so that the
two doors into this system can never disagree about what an agent may read.
"""

from apps.access.models import PermissionEffect
from apps.access.resolver import resolve_folder_effects
from apps.drive.models import Document, Folder
from apps.mcp import protocol
from apps.search import service

SEARCH = "search_documents"
SEARCH_FOLDER = "search_in_folder"
LIST_FOLDERS = "list_readable_folders"

DEFAULT_LIMIT = 8
MAX_LIMIT = 50

SEARCHING_TOOLS = frozenset({SEARCH, SEARCH_FOLDER})

QUERY_SCHEMA = {
    "type": "string",
    "description": "What to look for, in natural language.",
    "minLength": 1,
}

LIMIT_SCHEMA = {
    "type": "integer",
    "description": f"How many passages to return at most, from 1 to {MAX_LIMIT}.",
    "minimum": 1,
    "maximum": MAX_LIMIT,
    "default": DEFAULT_LIMIT,
}


def catalogue():
    """Describe every tool this server offers.

    The descriptions are written for a model that has never seen this system:
    each says what the tool returns and what it will not do, because a caller
    that misreads a tool wastes a turn discovering it.
    """
    return [
        {
            "name": SEARCH,
            "title": "Search documents",
            "description": (
                "Search every document this agent is allowed to read and return the "
                "passages that best answer the query. Results carry the text itself, "
                "so a further fetch is not needed. Documents the owner has not granted "
                "to this agent are never searched and never mentioned."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"query": QUERY_SCHEMA, "limit": LIMIT_SCHEMA},
                "required": ["query"],
            },
        },
        {
            "name": SEARCH_FOLDER,
            "title": "Search inside one folder",
            "description": (
                "Search only within one folder and everything below it. Use it to keep "
                "an answer to one subject area when the folder is known. A folder that "
                "does not exist and one this agent may not read both return nothing."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": QUERY_SCHEMA,
                    "folder_id": {
                        "type": "string",
                        "description": f"The id of the folder, as given by {LIST_FOLDERS}.",
                    },
                    "limit": LIMIT_SCHEMA,
                },
                "required": ["query", "folder_id"],
            },
        },
        {
            "name": LIST_FOLDERS,
            "title": "List readable folders",
            "description": (
                "List the folders this agent may read, each with its id, its name and "
                "its parent, so that a search can be narrowed to one of them. Folders "
                "the agent cannot read are left out entirely."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def call(agent, name, arguments):
    """Run one tool on behalf of an agent.

    Takes the calling agent, the tool name and its arguments. Returns the
    structured result, raising RpcError for a tool that does not exist or
    arguments that cannot be read.
    """
    if name == SEARCH:
        return {"results": search(agent, arguments)}
    if name == SEARCH_FOLDER:
        return {"results": search(agent, arguments, folder_required=True)}
    if name == LIST_FOLDERS:
        return {"folders": readable_folders(agent)}
    raise protocol.RpcError(protocol.INVALID_PARAMS, f"There is no tool called {name}")


def search(agent, arguments, folder_required=False):
    """Answer one search, with or without a folder to stay within."""
    query = read_query(arguments)
    limit = read_limit(arguments)
    folder_id = arguments.get("folder_id")
    if folder_required and not folder_id:
        raise protocol.RpcError(protocol.INVALID_PARAMS, "A folder_id is required")
    return service.search(agent, query, limit, folder_id=folder_id if folder_id else None)


def read_query(arguments):
    """Take the query out of the arguments, or say why it cannot be used."""
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise protocol.RpcError(protocol.INVALID_PARAMS, "A non-empty query is required")
    return query


def read_limit(arguments):
    """Take the limit out of the arguments, holding it inside its bounds.

    A caller asking for more than the ceiling is refused rather than quietly
    served less, because an agent that believes it saw everything and did not
    will answer from a gap without knowing.
    """
    limit = arguments.get("limit", DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise protocol.RpcError(protocol.INVALID_PARAMS, "The limit has to be a whole number")
    if limit < 1 or limit > MAX_LIMIT:
        raise protocol.RpcError(
            protocol.INVALID_PARAMS, f"The limit has to be between 1 and {MAX_LIMIT}"
        )
    return limit


def readable_folders(agent):
    """List the folders one agent reaches, resolved rules and all.

    A folder is listed when the rules resolve to allow, or when a document
    inside it was granted on its own: an agent told nothing about that folder
    could never narrow a search to the one document it is there to read. The
    parent is reported only when the agent reaches it too, so that the shape of
    the tree above never leaks through a broken link.
    """
    effects = resolve_folder_effects(agent)
    allowed = {
        folder_id for folder_id, effect in effects.items() if effect == PermissionEffect.ALLOW
    }
    allowed.update(
        Document.objects.filter(
            permissions__agent=agent, permissions__effect=PermissionEffect.ALLOW
        ).values_list("folder_id", flat=True)
    )
    folders = Folder.objects.filter(pk__in=allowed).order_by("name")
    return [
        {
            "folder_id": str(folder.pk),
            "name": folder.name,
            "parent_id": str(folder.parent_id) if folder.parent_id in allowed else None,
        }
        for folder in folders
    ]
