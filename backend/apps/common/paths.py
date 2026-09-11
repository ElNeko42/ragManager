"""Recognising the endpoint an address belongs to, slash or no slash."""

from django.conf import settings


def is_mcp(path):
    """Report whether an address is the MCP endpoint.

    Takes the path of a request. Both spellings count: the endpoint is
    published as a resource identifier without a trailing slash, which is the
    form the specification asks for, and clients are free to use either. A
    check written as a plain prefix match answers no to the very address this
    server tells them to use.
    """
    return f"/{path.strip('/')}/".startswith(settings.MCP_PATH)
