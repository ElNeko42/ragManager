"""WSGI entry point used by gunicorn."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()

# Each web worker loads the embedding models it will search with as it
# starts, rather than on its first query. Loading takes about ten seconds
# here, which is long enough for a connector to decide the server is not
# answering and ask again; paid at boot, it is paid before anyone is waiting.
from apps.ingestion.embeddings import warm_up  # noqa: E402

warm_up()
