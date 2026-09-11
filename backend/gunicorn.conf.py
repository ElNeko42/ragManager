"""How the web process is run when it is reachable by somebody else.

Gunicorn's own defaults are a single synchronous worker that gives up on a
request after thirty seconds and closes every connection it answers. That is
wrong for this server on three counts. The first search on a cold process
loads an embedding model, which takes longer than thirty seconds when the
model has to be fetched, and a worker killed in the middle of that answers
with nothing and starts loading again on the next call. A single worker with
no threads answers one request at a time, so an agent embedding a query holds
up the owner's panel until it is done. And an MCP client sends a handshake
and then its calls one after another, so a connection closed after each
costs it a fresh one every time.
"""

import multiprocessing
import os


def env_int(name, default):
    """Read a whole number from the environment, falling back when blank."""
    value = os.environ.get(name, "")
    return int(value) if value.strip().isdigit() else default


bind = "0.0.0.0:8000"

# A few threads per worker rather than many workers: each worker that embeds
# holds its own copy of every model an agent has searched, and torch releases
# the interpreter lock while it works, so threads share one copy and still
# overlap. Two workers is enough for one to answer while the other loads.
workers = env_int("WEB_WORKERS", min(2, multiprocessing.cpu_count()))
threads = env_int("WEB_THREADS", 4)
worker_class = "gthread"

timeout = env_int("WEB_TIMEOUT_SECONDS", 180)
graceful_timeout = env_int("WEB_GRACEFUL_TIMEOUT_SECONDS", 30)
keepalive = env_int("WEB_KEEPALIVE_SECONDS", 15)

# Requests are reached through a proxy on the same machine; its address is
# the one to trust for the forwarded scheme and client, not any address.
forwarded_allow_ips = os.environ.get("WEB_FORWARDED_ALLOW_IPS", "*")

accesslog = "-" if os.environ.get("WEB_ACCESS_LOG", "").lower() in {"1", "true", "yes"} else None
loglevel = os.environ.get("WEB_LOG_LEVEL", "info")

warm_models = os.environ.get("WEB_WARM_MODELS", "true").lower() not in {"0", "false", "no"}


def post_worker_init(worker):
    """Start loading the embedding models as soon as a worker is up.

    The first search a worker answers otherwise loads its model while the
    caller waits, and a connector that gives up after ten seconds reports the
    server as broken. Loading runs on a thread of its own so that the worker
    takes requests straight away; a search arriving before the load is done
    waits for it rather than starting a second one. Switched off with
    WEB_WARM_MODELS=false on a machine that would rather pay on first use.
    """
    if not warm_models:
        return
    import threading

    def warm():
        """Load the models, reporting what was loaded."""
        import django

        django.setup()
        from django.db import connection

        from apps.ingestion.embeddings import warm_local_models

        try:
            loaded = warm_local_models()
        except Exception:
            worker.log.exception("Could not warm the embedding models")
            return
        finally:
            # A thread that opened a database connection has to close it,
            # since nothing else will reuse it.
            connection.close()
        worker.log.info("Warmed %d embedding model(s): %s", len(loaded), ", ".join(loaded))

    threading.Thread(target=warm, name="warm-models", daemon=True).start()
