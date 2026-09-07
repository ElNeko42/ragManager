# ragManager

Self-hosted RAG storage with a Google Drive style management panel, built so
that the primary consumer is an **external AI agent** rather than a person in a
chat window. There is no built-in chat: documents are uploaded and organised
through the web panel, and agents such as Claude or Gemini query them through
the MCP server.

Permissions are granted to agents, each with its own identity and token, not to
people.

## Stack

| Piece | Choice |
| --- | --- |
| API | Django + Django REST Framework |
| Web panel | Vue 3 single page application |
| Relational data | PostgreSQL |
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
through an SSH tunnel rather than opening the ports, and never expose the
development settings module to the internet.

If any of those ports is already taken on the host, change the matching
`*_HOST_PORT` value in `.env`. Only the published side moves; the containers
keep talking to each other on their standard ports.

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
not, naming the one that failed. The web panel renders the same report on its
front page.

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
