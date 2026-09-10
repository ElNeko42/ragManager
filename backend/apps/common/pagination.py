"""How long listings are cut into pages."""

from django.conf import settings
from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    """Cuts a listing into pages of a size the caller may choose.

    An instance holding thousands of documents cannot answer a listing with
    all of them: the query, the serialisation and the browser all pay for it,
    and the panel shows one folder at a time anyway. The ceiling on the page
    size is what keeps a caller from asking for the whole table by naming a
    huge page.
    """

    page_size = settings.PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = settings.MAX_PAGE_SIZE
