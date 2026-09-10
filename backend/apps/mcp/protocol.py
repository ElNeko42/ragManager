"""The JSON-RPC 2.0 envelope that every MCP message travels in.

Kept apart from the tools so that the rules of the transport and the work the
server actually does never get tangled: this module knows nothing about
searching, and the tools know nothing about request ids.
"""

VERSION = "2.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
PREFERRED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


class RpcError(Exception):
    """A failure that has to reach the caller as a JSON-RPC error object."""

    def __init__(self, code, message):
        """Store the code and the sentence explaining the refusal."""
        super().__init__(message)
        self.code = code
        self.message = message


def result(request_id, payload):
    """Wrap a successful answer in its envelope."""
    return {"jsonrpc": VERSION, "id": request_id, "result": payload}


def error(request_id, code, message):
    """Wrap a failure in its envelope.

    The id is echoed even when it is null, because a caller matching answers to
    calls has no other way to know which one failed.
    """
    return {"jsonrpc": VERSION, "id": request_id, "error": {"code": code, "message": message}}


def is_notification(message):
    """Report whether a message expects no answer at all.

    A notification is a call without an id. Answering one is a protocol
    violation, so the difference decides whether anything is sent back.
    """
    return isinstance(message, dict) and "id" not in message


def read_call(message):
    """Pull the method and parameters out of one incoming message.

    Takes the decoded message. Returns the method name and its parameters,
    raising RpcError when the message is not a call this server can read.
    """
    if not isinstance(message, dict):
        raise RpcError(INVALID_REQUEST, "A message has to be an object")
    if message.get("jsonrpc") != VERSION:
        raise RpcError(INVALID_REQUEST, f"Only JSON-RPC {VERSION} is spoken here")
    method = message.get("method")
    if not isinstance(method, str) or not method:
        raise RpcError(INVALID_REQUEST, "A message has to name a method")
    params = message.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "Parameters have to be an object")
    return method, params


def negotiate_version(asked):
    """Choose the protocol version to speak with one client.

    Takes what the client asked for. Returns the same version when it is one
    this server knows, and otherwise the newest it does know, which the client
    is then free to accept or to disconnect over.
    """
    if asked in SUPPORTED_PROTOCOL_VERSIONS:
        return asked
    return PREFERRED_PROTOCOL_VERSION
