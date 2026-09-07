# ragManager

Self-hosted RAG storage with a Google Drive style management panel, built so
that the primary consumer is an **external AI agent** rather than a person in a
chat window. There is no built-in chat: documents are uploaded and organised
through the web panel, and agents such as Claude or Gemini query them through
the MCP server.

Permissions are granted to agents, each with its own identity and token, not to
people.

## Status

Under construction. The management API, authentication and the ingestion
pipeline work; the MCP server and the permission resolver do not exist yet, so
no agent can query documents at the moment. The web panel currently renders
only the health report.

## Stack

| Piece | Choice |
| --- | --- |
| API | Django + Django REST Framework |
| Web panel | Vue 3 single page application |
| Relational data | PostgreSQL 15 or newer |
| Vectors | Qdrant |
| Files | S3 compatible object storage (MinIO when self-hosting) |
| Queue | Celery over Redis |

Everything runs from a single `docker compose up`.

## Quickstart

```sh
cp .env.example .env
```

Fill in the empty values. The secrets can be generated with:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # MINIO_ROOT_PASSWORD
```

`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` are the credentials of the MinIO
service itself; `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` are what the
application uses to talk to it. When self-hosting with the bundled MinIO, set
them to the same pair.

Then:

```sh
docker compose up --build
```

| Service | Address |
| --- | --- |
| Web panel | http://localhost:5173 |
| API | http://localhost:8000 |
| Health report | http://localhost:8000/health/ |
| MinIO console | http://localhost:9001 |
| Qdrant dashboard | http://localhost:6333/dashboard |

Every port is published on `127.0.0.1` only. On a remote server, reach them
through an SSH tunnel rather than opening the ports.

## Development mode

`DJANGO_SETTINGS_MODULE` is the only switch. It decides the debug pages, the
server and the static file handling together, so there is no combination of
variables that serves debug tracebacks while looking like production:

| Value | Debug pages | Server |
| --- | --- | --- |
| `config.settings.prod` (default) | off | gunicorn |
| `config.settings.dev` | on | runserver, with autoreload |

The panel has the same pair. `FRONTEND_TARGET=production` (the default) builds
the application and serves the result with nginx; `FRONTEND_TARGET=development`
runs the Vite server with hot reload. Both listen on the same port and both
forward `/api/` and `/health/` to the backend, so the address does not change
when you switch.

Production settings refuse to start without a secret key, without allowed
hosts, or with `*` among them. Development settings refuse to start at all when
`PUBLIC_HOST` is set, because that combination puts debug tracebacks on a
public address; `ALLOW_PUBLIC_DEBUG=true` overrides it if you accept that.

`TRUSTED_PROXY_COUNT` is how many reverse proxies sit in front. It ships as `0`,
which makes rate limiting count the address the connection came from. Raise it
to the number of proxies you actually run: setting it higher than that lets a
caller forge the address it is counted under.

If any of those ports is already taken on the host, change the matching
`*_HOST_PORT` value in `.env`. Only the published side moves; the containers
keep talking to each other on their standard ports.

## Embedding providers

A collection names the model that produced its vectors. `local` runs a
sentence-transformers model inside the container and needs no account
anywhere; `api` points at any endpoint that speaks the OpenAI embeddings
shape, which covers most hosted providers as well as a model you run yourself.

`EMBEDDING_API_KEY` is the shared credential. A collection can carry its own by
setting `EMBEDDING_API_KEY_<NAME>` — the collection name upper cased with
hyphens turned into underscores, so `openai-large` reads
`EMBEDDING_API_KEY_OPENAI_LARGE`. Give each collection its own key when they
live at different providers, so one provider's credential is never sent to
another.

## Running behind a reverse proxy

Set `PUBLIC_HOST` in `.env` to the hostname the browser will use:

```
PUBLIC_HOST=rag.example.com
```

That single value adds the host to Django's `ALLOWED_HOSTS`, trusts
`https://<host>` for CSRF, honours the `X-Forwarded-Proto` header, and tells
the Vite dev server to accept the host and to open its hot reload socket
through the proxy.

An nginx virtual host that serves the panel and the API from the same origin:

```nginx
server {
    listen 80;
    server_name rag.example.com;

    client_max_body_size 512M;

    location ~ ^/(health|api|admin|static)/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
    }

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then issue the certificate with `certbot --nginx -d rag.example.com --redirect`.

Serving both from one origin keeps the session cookie same-site, so the browser
needs no CORS exception at all.

## Health report

`GET /health/` probes PostgreSQL, Redis, Qdrant and the object storage bucket.
It answers `200` when every service is reachable and `503` as soon as one is
not, naming the one that failed. The reason a probe failed is added only for a
signed in owner, since driver errors quote hosts, users and endpoints. The web
panel renders the same report on its front page.

## Project layout

```
backend/            Django project
  config/           settings, routing, Celery application, health probes
frontend/           Vue 3 single page application
docker-compose.yml  postgres, redis, qdrant, minio, backend, worker, frontend
```

The backend image carries a single application build with two entry points,
`web` and `worker`, because the embedding model is needed both to ingest
documents and to vectorise incoming agent queries.

## Licence

MIT. See [LICENSE](LICENSE).
