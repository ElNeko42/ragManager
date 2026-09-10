"""Tests for the MCP endpoint: the protocol it speaks and what it refuses."""

import json
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from config.middleware import RequestSizeLimitMiddleware

from apps.access.models import Permission, PermissionEffect
from apps.agents.models import Agent
from apps.agents.tokens import issue_token
from apps.drive.models import Collection, Document, Folder, ProcessingStatus
from apps.ingestion.embeddings import EmbeddingError
from apps.mcp import protocol, tools

TEST_RATES = {"search": "1000/min"}


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class McpTransportTests(TestCase):
    """What the endpoint answers before any tool is reached."""

    def setUp(self):
        """Issue a token for an agent that has been granted nothing."""
        self.agent = Agent.objects.create(name="caller")
        self.token = issue_token(self.agent)[1]

    def rpc(self, payload, token=None):
        """Post one message as the agent under test."""
        return self.client.post(
            "/mcp/",
            json.dumps(payload),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {self.token if token is None else token}",
        )

    def test_a_call_without_a_token_is_refused(self):
        """The endpoint is a door for agents, so an anonymous caller never enters."""
        response = self.client.post(
            "/mcp/", "{}", content_type="application/json", secure=True
        )
        self.assertEqual(response.status_code, 401)

    def test_a_call_with_an_unknown_token_is_refused(self):
        """A revoked or invented token must not reach a single tool."""
        response = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="nonsense")
        self.assertEqual(response.status_code, 401)

    def test_initialize_answers_with_the_tools_capability(self):
        """A client that is not told tools exist never asks for their list."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).json()
        self.assertIn("tools", answer["result"]["capabilities"])

    def test_the_protocol_version_the_client_asked_for_is_agreed_to(self):
        """Answering with another version makes a strict client disconnect."""
        answer = self.rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            }
        ).json()
        self.assertEqual(answer["result"]["protocolVersion"], "2024-11-05")

    def test_an_unknown_protocol_version_falls_back_to_a_known_one(self):
        """The client decides whether to accept it, but has to be told which."""
        answer = self.rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "1999-01-01"},
            }
        ).json()
        self.assertIn(answer["result"]["protocolVersion"], protocol.SUPPORTED_PROTOCOL_VERSIONS)

    def test_a_notification_is_acknowledged_without_an_answer(self):
        """Answering a message that carries no id breaks the protocol."""
        response = self.rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.content)

    def test_a_body_that_is_not_json_is_reported_as_a_parse_error(self):
        """A client sending rubbish has to learn that, not read a stack trace."""
        response = self.client.post(
            "/mcp/",
            "{not json",
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.json()["error"]["code"], protocol.PARSE_ERROR)

    def test_an_unknown_method_is_reported_as_such(self):
        """A caller has to tell a method this server lacks from one that failed."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 3, "method": "resources/list"}).json()
        self.assertEqual(answer["error"]["code"], protocol.METHOD_NOT_FOUND)

    def test_the_id_of_a_failed_call_comes_back_with_it(self):
        """A client matching answers to calls cannot tell which one failed without it."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 7, "method": "resources/list"}).json()
        self.assertEqual(answer["id"], 7)

    def test_ping_answers_an_empty_result(self):
        """Clients use it to check the connection is still worth holding."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 4, "method": "ping"}).json()
        self.assertEqual(answer["result"], {})

    def test_a_message_of_another_protocol_is_refused(self):
        """Reading a message whose envelope is unknown guesses at its meaning."""
        answer = self.rpc({"jsonrpc": "1.0", "id": 5, "method": "ping"}).json()
        self.assertEqual(answer["error"]["code"], protocol.INVALID_REQUEST)

    def test_a_batch_is_refused_rather_than_half_answered(self):
        """Answering the first of several calls silently loses the rest."""
        answer = self.rpc([{"jsonrpc": "2.0", "id": 1, "method": "ping"}]).json()
        self.assertEqual(answer["error"]["code"], protocol.INVALID_REQUEST)

    def test_a_listening_stream_is_declined_and_not_left_open(self):
        """A client waiting on a stream this server never writes to would hang."""
        response = self.client.get(
            "/mcp/", secure=True, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 405)

    def test_every_offered_tool_declares_a_schema_for_its_arguments(self):
        """A tool without a schema is one a model has to guess how to call."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 6, "method": "tools/list"}).json()
        for tool in answer["result"]["tools"]:
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_the_three_tools_are_offered(self):
        """The panel promises these three, so the server has to answer with them."""
        answer = self.rpc({"jsonrpc": "2.0", "id": 6, "method": "tools/list"}).json()
        self.assertEqual(
            {tool["name"] for tool in answer["result"]["tools"]},
            {tools.SEARCH, tools.SEARCH_FOLDER, tools.LIST_FOLDERS},
        )


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class McpToolTests(TestCase):
    """What the tools return, and what they refuse to say."""

    def setUp(self):
        """Grant one agent one folder and leave a sibling folder ungranted."""
        self.collection = Collection.objects.get(is_default=True)
        self.root = Folder.objects.get(parent__isnull=True)
        self.granted = Folder.objects.create(
            name="Granted", parent=self.root, collection=self.collection
        )
        self.hidden = Folder.objects.create(
            name="Hidden", parent=self.root, collection=self.collection
        )
        self.agent = Agent.objects.create(name="caller")
        self.token = issue_token(self.agent)[1]
        Permission.objects.create(
            agent=self.agent, folder=self.granted, effect=PermissionEffect.ALLOW
        )

    def call(self, name, arguments):
        """Call one tool and return the decoded answer."""
        return self.client.post(
            "/mcp/",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            ),
            content_type="application/json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()

    def test_only_the_granted_folder_is_listed(self):
        """A folder an agent cannot read must not even be named to it."""
        answer = self.call(tools.LIST_FOLDERS, {})
        names = {folder["name"] for folder in answer["result"]["structuredContent"]["folders"]}
        self.assertEqual(names, {"Granted"})

    def test_a_listed_folder_reports_no_parent_the_agent_cannot_reach(self):
        """A parent id the agent may not read leaks the shape of the tree above it."""
        answer = self.call(tools.LIST_FOLDERS, {})
        listed = answer["result"]["structuredContent"]["folders"][0]
        self.assertIsNone(listed["parent_id"])

    def test_a_folder_granted_only_through_a_document_is_listed(self):
        """Without its folder, the one document the agent may read is unreachable."""
        document = Document.objects.create(
            folder=self.hidden,
            name="invoice.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="invoice.txt",
            processing_status=ProcessingStatus.READY,
        )
        Permission.objects.create(
            agent=self.agent, document=document, effect=PermissionEffect.ALLOW
        )
        answer = self.call(tools.LIST_FOLDERS, {})
        names = {folder["name"] for folder in answer["result"]["structuredContent"]["folders"]}
        self.assertEqual(names, {"Granted", "Hidden"})

    def test_a_search_result_is_returned_both_as_text_and_as_data(self):
        """A client without structured support still has to be able to read it."""
        with patch("apps.mcp.tools.service.search", return_value=[{"text": "found"}]):
            answer = self.call(tools.SEARCH, {"query": "anything"})
        result = answer["result"]
        self.assertEqual(result["structuredContent"]["results"], [{"text": "found"}])
        self.assertIn("found", result["content"][0]["text"])

    def test_the_limit_asked_for_reaches_the_search(self):
        """A limit quietly ignored makes an agent believe it saw everything."""
        with patch("apps.mcp.tools.service.search", return_value=[]) as search:
            self.call(tools.SEARCH, {"query": "anything", "limit": 3})
        self.assertEqual(search.call_args.args[2], 3)

    def test_a_limit_above_the_ceiling_is_refused(self):
        """Serving fewer than asked without saying so hides the gap in the answer."""
        answer = self.call(tools.SEARCH, {"query": "anything", "limit": tools.MAX_LIMIT + 1})
        self.assertEqual(answer["error"]["code"], protocol.INVALID_PARAMS)

    def test_a_search_without_a_query_is_refused(self):
        """An empty query embeds nothing and would return an arbitrary sample."""
        answer = self.call(tools.SEARCH, {"query": "   "})
        self.assertEqual(answer["error"]["code"], protocol.INVALID_PARAMS)

    def test_searching_a_folder_without_naming_one_is_refused(self):
        """Falling back to the whole store would widen what the caller asked for."""
        answer = self.call(tools.SEARCH_FOLDER, {"query": "anything"})
        self.assertEqual(answer["error"]["code"], protocol.INVALID_PARAMS)

    def test_the_named_folder_reaches_the_search(self):
        """A folder that never arrives turns a narrow search into a wide one."""
        with patch("apps.mcp.tools.service.search", return_value=[]) as search:
            self.call(
                tools.SEARCH_FOLDER, {"query": "anything", "folder_id": str(self.granted.pk)}
            )
        self.assertEqual(search.call_args.kwargs["folder_id"], str(self.granted.pk))

    def test_a_tool_that_does_not_exist_is_refused(self):
        """A model inventing a tool name has to be told, not silently answered."""
        answer = self.call("delete_everything", {})
        self.assertEqual(answer["error"]["code"], protocol.INVALID_PARAMS)

    def test_an_unreachable_embedding_model_fails_the_tool_not_the_call(self):
        """A broken dependency is something the model can retry; a broken call is not."""
        with patch("apps.mcp.tools.service.search", side_effect=EmbeddingError("down")):
            answer = self.call(tools.SEARCH, {"query": "anything"})
        self.assertTrue(answer["result"]["isError"])
        self.assertNotIn("error", answer)


class LengthExemptionTests(TestCase):
    """Which paths may send a body without declaring how long it is."""

    def setUp(self):
        """Build the middleware over a handler that just reports success."""
        self.factory = RequestFactory()
        self.middleware = RequestSizeLimitMiddleware(lambda request: HttpResponse(status=204))

    def chunked(self, path):
        """Send a body to one path the way a streaming client would.

        The test client always declares a length, so the request is built by
        hand with that header removed: a chunked body carries no length, and
        that absence is the whole point of the rule being tested.
        """
        request = self.factory.post(path, data="{}", content_type="application/json")
        request.META.pop("CONTENT_LENGTH", None)
        return self.middleware(request)

    def test_a_body_without_a_length_is_refused_everywhere_else(self):
        """A body of unknown size walks straight past the only size limit there is."""
        self.assertEqual(self.chunked("/api/search/").status_code, 411)

    def test_the_mcp_endpoint_accepts_a_body_without_a_length(self):
        """A streaming client sends exactly that, and would be refused every call."""
        self.assertEqual(self.chunked(settings.MCP_PATH).status_code, 204)

    def test_the_mcp_endpoint_still_refuses_an_oversized_body(self):
        """Lifting the demand for a length must not lift the limit itself."""
        request = self.factory.post(settings.MCP_PATH, data="{}", content_type="application/json")
        request.META["CONTENT_LENGTH"] = str(settings.MAX_UPLOAD_BYTES * 2)
        self.assertEqual(self.middleware(request).status_code, 413)
