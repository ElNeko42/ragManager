"""The single endpoint an MCP client connects to.

The transport is the streamable HTTP one, answered in its JSON form: a client
posts one JSON-RPC message and gets one JSON answer back. The specification
allows a server to reply either with a JSON body or with an event stream, and
JSON is chosen here because this server holds no state between calls and has
nothing to push, while an event stream would rule out the plain WSGI worker
that serves the rest of the API.
"""

import json
import logging

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.permissions import IsAgent
from apps.ingestion.embeddings import EmbeddingError
from apps.mcp import protocol, tools
from apps.search.views import SearchThrottle

logger = logging.getLogger(__name__)

SERVER_NAME = "ragManager"
SERVER_TITLE = "ragManager document store"

INSTRUCTIONS = (
    "This server searches a private document store. Each agent sees only what the "
    "owner granted it, so a search that returns nothing means nothing was granted "
    "or nothing matched, never that the store is empty. Passages come back with "
    "their text, so no second call is needed to read them."
)


class McpView(APIView):
    """Speaks MCP over HTTP to an agent holding a token."""

    permission_classes = [IsAgent]

    message = None
    is_searching = False

    def get_throttles(self):
        """Meter only the calls that cost an embedding.

        Listing tools or opening a connection is free, and metering it would
        spend an agent's allowance on the handshake it has to perform before it
        can ask anything at all.
        """
        return [SearchThrottle()] if self.is_searching else []

    def initial(self, request, *args, **kwargs):
        """Read the message before the throttles decide whether it is metered."""
        self.message = self.decode(request)
        self.is_searching = self.costs_an_embedding(self.message)
        super().initial(request, *args, **kwargs)

    def decode(self, request):
        """Turn the request body into a message, or into nothing readable."""
        try:
            return json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def costs_an_embedding(self, message):
        """Report whether a message asks for work that embeds a query."""
        if not isinstance(message, dict) or message.get("method") != "tools/call":
            return False
        params = message.get("params")
        return isinstance(params, dict) and params.get("name") in tools.SEARCHING_TOOLS

    def get(self, request):
        """Refuse the stream this server does not open.

        A client may open a listening stream on this endpoint; the
        specification lets a server that has nothing to push decline, and this
        one answers every call in the reply to that call.
        """
        return self.rpc(
            None,
            protocol.INVALID_REQUEST,
            "This server answers in the reply to each call and opens no stream",
            status=405,
        )

    def delete(self, request):
        """Refuse to end a session that was never started."""
        return self.rpc(
            None, protocol.INVALID_REQUEST, "This server keeps no session to end", status=405
        )

    def post(self, request):
        """Answer one JSON-RPC message.

        Takes the posted message. Returns its answer, an empty acknowledgement
        when the message was a notification, or a JSON-RPC error describing why
        nothing could be done with it.
        """
        message = self.message
        if message is None:
            return self.rpc(None, protocol.PARSE_ERROR, "The body is not valid JSON")
        if isinstance(message, list):
            return self.rpc(
                None, protocol.INVALID_REQUEST, "Send one message at a time; batches are not read"
            )
        try:
            method, params = protocol.read_call(message)
        except protocol.RpcError as failure:
            return self.rpc(self.identifier(message), failure.code, failure.message)

        if protocol.is_notification(message):
            return Response(status=202)

        request_id = message.get("id")
        try:
            return Response(protocol.result(request_id, self.dispatch_method(method, params)))
        except protocol.RpcError as failure:
            return self.rpc(request_id, failure.code, failure.message)
        except Exception:
            logger.exception("An MCP call failed unexpectedly: %s", method)
            return self.rpc(request_id, protocol.INTERNAL_ERROR, "The call could not be completed")

    def identifier(self, message):
        """Return the id of a message that may not be well formed at all."""
        return message.get("id") if isinstance(message, dict) else None

    def dispatch_method(self, method, params):
        """Run one MCP method and return what it answers with."""
        if method == "initialize":
            return self.initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": tools.catalogue()}
        if method == "tools/call":
            return self.call_tool(params)
        raise protocol.RpcError(protocol.METHOD_NOT_FOUND, f"Unknown method: {method}")

    def initialize(self, params):
        """Introduce the server and agree on a protocol version."""
        return {
            "protocolVersion": protocol.negotiate_version(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": SERVER_NAME,
                "title": SERVER_TITLE,
                "version": settings.RAGMANAGER_VERSION,
            },
            "instructions": INSTRUCTIONS,
        }

    def call_tool(self, params):
        """Run the named tool for the agent that asked.

        A tool that fails because a dependency is down answers as a failed tool
        result rather than as a protocol error, so that the calling model is
        told what went wrong and can decide to retry, instead of its client
        treating the conversation itself as broken.
        """
        name = params.get("name")
        if not isinstance(name, str):
            raise protocol.RpcError(protocol.INVALID_PARAMS, "A tool name is required")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise protocol.RpcError(protocol.INVALID_PARAMS, "Arguments have to be an object")
        try:
            payload = tools.call(self.request.user, name, arguments)
        except EmbeddingError as failure:
            return self.tool_failure(f"The embedding model is unavailable: {failure}")
        return {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
            "structuredContent": payload,
            "isError": False,
        }

    def tool_failure(self, message):
        """Report a tool that could not do its work, without breaking the call."""
        return {"content": [{"type": "text", "text": message}], "isError": True}

    def rpc(self, request_id, code, message, status=200):
        """Send a JSON-RPC error, with the HTTP status the transport calls for."""
        return Response(protocol.error(request_id, code, message), status=status)
