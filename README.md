# ragManager

Self-hosted RAG storage with a Google Drive style management panel, built so
that the primary consumer is an **external AI agent** rather than a person in a
chat window. There is no built-in chat: documents are uploaded and organised
through the web panel, and agents such as Claude or Gemini query them through
the MCP server.

Permissions are granted to agents, each with its own identity and token, not to
people.

## Status

Under construction. The management API, authentication, the ingestion
pipeline, the permission resolver, the search endpoint and the MCP server
work. The web panel covers documents and folders, agents and their tokens,
permissions, and registering the embedding models that index it all.

An external agent can reach the store either through the MCP endpoint or by
calling the search endpoint directly with its token. Both doors resolve
permissions the same way, from the same resolver.

The ingestion queue retries a dependency that was unreachable, the listings
are paged, every agent query is written down, and the chunk size is a setting
of each collection rather than a constant.

What it does not have yet: there are no tests in front of the panel, and the
panel does not yet surface the query log or the reprocess button the API
offers.

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

Every port is published on `127.0.0.1` only. On a remote server, reach them
through an SSH tunnel rather than opening the ports.

## Qdrant

Qdrant is not part of this compose file. It is named in `QDRANT_URL` and
`QDRANT_API_KEY` and can be a container of your own, a Qdrant on another host
or a hosted one, which lets one Qdrant serve several projects instead of each
raising its own. Collections are named after the embedding model, so projects
sharing an instance do not collide.

The collection is created on first use, with the vector size fixed by the
model, so nothing has to be prepared by hand.

Two things to watch:

- **The port has to be in the URL.** The client assumes `6333` when the URL
  names no port, so a Qdrant behind a TLS proxy needs `https://host:443`, not
  `https://host`.
- **Match the client to the server.** `qdrant-client` refuses to guarantee
  anything when the major versions differ or the minor versions differ by more
  than one, and says so in a warning rather than by failing.

## Development mode

`DJANGO_SETTINGS_MODULE` is the only switch. It decides the debug pages, the
server and the static file handling together, so there is no combination of
variables that serves debug tracebacks while looking like production:

| Value | Debug pages | Server |
| --- | --- | --- |
| `config.settings.prod` (default) | off | gunicorn |
| `config.settings.dev` | on | runserver, with autoreload |

The compose file mounts `./backend` into both the backend and the worker, so
the code they run is the code in the repository. Under production settings
gunicorn reads it once at boot and the worker imports its tasks once, which
means **a change to the backend is not running until those two are restarted**:

```sh
docker compose restart backend worker
```

The tests will not tell you otherwise — `manage.py test` starts a new process
and therefore always runs the code on disk, so a suite can pass against a
change the running server has never loaded. Development settings avoid this
entirely: runserver reloads itself.

The panel has the same pair. `FRONTEND_TARGET=production` (the default) builds
the application and serves the result with nginx; `FRONTEND_TARGET=development`
runs the Vite server with hot reload. Both listen on the same port and both
forward `/api/` and `/health/` to the backend, so the address does not change
when you switch.

Production settings refuse to start without a secret key, without allowed
hosts, or with `*` among them. Development settings refuse to start at all when
`PUBLIC_HOST` is set, because that combination puts debug tracebacks on a
public address; `ALLOW_PUBLIC_DEBUG=true` overrides it if you accept that.

Under production settings gunicorn is configured by `backend/gunicorn.conf.py`
rather than by its defaults, which are one synchronous worker, a thirty second
timeout and no keep-alive. `WEB_WORKERS` (default 2) and `WEB_THREADS`
(default 4) set how many requests are answered at once; prefer threads, because
every worker that has answered a search holds its own copy of each embedding
model, which is close to a gigabyte of memory per worker with torch loaded.
`WEB_TIMEOUT_SECONDS` (default 180) has to cover loading a model on a cold
process. Each worker starts loading the local models of the registered
collections in the background as soon as it boots, so the first search after a
restart does not pay for it; `WEB_WARM_MODELS=false` turns that off on a machine
that would rather pay on first use.

`TRUSTED_PROXY_COUNT` is how many reverse proxies sit in front. It ships as `0`,
which makes rate limiting count the address the connection came from. Raise it
to the number of proxies you actually run: setting it higher than that lets a
caller forge the address it is counted under.

If any of those ports is already taken on the host, change the matching
`*_HOST_PORT` value in `.env`. Only the published side moves; the containers
keep talking to each other on their standard ports.

## How text is split

A document is embedded in pieces, and the size of a piece is the setting that
decides most of what an agent ends up reading. Every model reads only so many
tokens of a piece and silently ignores the rest, so a chunk longer than the
model reads is stored and returned in full while only its opening influenced
the vector: the passage that answers the question is there, and it scores
badly. The default model here reads 256 tokens, which is roughly 200 words.

### Telling a model which end it is reading

A family of embedding models is trained to be told whether it is reading a
question or an answer, and asking one without saying so measures the two as
though they were the same kind of thing. `query_prefix` and `passage_prefix` on
a collection carry those words — `query: ` and `passage: ` for the e5 family,
empty for a model that was never trained on them. They live on the collection
because they belong to the model, which keeps a table of vendors and their
habits out of this project.

### The size that actually matters is tokens, not words

A word count is a stand-in for the real limit, and a poor one: a model trained
on English spends far more tokens per word on Spanish than on the text it was
measured with. On this instance a 228 word chunk cost 620 tokens against a
model that reads 256, so three fifths of every chunk was stored, returned and
never embedded — which is how a telephone number sitting at the end of a chunk
ends up behind passages about something else entirely.

A collection whose model runs in this process is asked directly how much it
reads and how many tokens a piece of text costs, so nothing has to be assumed
about the language. One behind an endpoint cannot be asked and uses
`max_tokens` if it was told. The word count is a target the chunk may overshoot
to reach a sentence boundary; the token budget is a ceiling it never passes,
because everything past it is text nobody reads.

`CHUNK_WORDS` and `CHUNK_OVERLAP_WORDS` set the instance default. A collection
may name its own size, which is where it belongs, since the limit is the
model's rather than the instance's. Chunks are closed at a paragraph or a
sentence boundary near the target rather than at an exact word count, because
a chunk that begins mid sentence embeds as a fragment. The overlap is what
keeps an idea cut in half by a boundary whole in one of the two neighbours.

Changing the size does not re-split what is already indexed. Documents keep
the chunks they were vectorised with until each one is queued again, which the
reprocess route does:

```sh
curl -X POST -b cookies.txt -H "X-CSRFToken: $TOKEN" \
  https://your.host/api/documents/<id>/reprocess/
```

## Telling a near miss from an answer

A search returns its closest matches, and closest is not the same as relevant.
Asked about something the store knows nothing about, it answers with whatever
was least unlike the question, and an agent with no way to tell reads that as
an answer. `minimum_score` on a collection is the floor a passage has to
clear. It belongs to the collection because every model scores on its own
scale: on this instance a query about nothing at all scored up to 0.39 against
one model and 0.52 against another, while real answers started at 0.59 and
0.69 respectively. Measure yours the same way before setting it, and leave it
empty to return everything, which is what an instance does until somebody
decides otherwise.

For the same reason a result carries `rank_in_collection` beside its `score`.
A reader comparing 0.44 from one model against 0.61 from another is comparing
two scales that have nothing to do with each other; the rank says where a
passage stood among the ones it can be compared against. The tool description
says so too, since the reader is usually a model.

## When something in the queue is down

A run that fails because a dependency could not be reached is queued again
after a growing wait, capped by `INGESTION_RETRY_MAX_BACKOFF_SECONDS` and
given up on after `INGESTION_MAX_RETRIES` attempts. A vector store restarting
for a minute therefore costs a document nothing.

A run that fails because of the file itself is not retried: a format with no
extractor, a model whose width disagrees with the collection, a rejected
credential. Those fail identically on every attempt, so the document is marked
failed with the reason, and queueing it again is a deliberate act once the
cause is fixed. The attempts a run took are kept on the job.

Before registering a model, or after changing a provider, ask it directly
rather than finding out through a failed job hours later:

```sh
docker compose exec backend python manage.py check_embeddings <collection>
```

It embeds two sentences, reports the width and the round trip, and says
whether a failure is something to retry or something to correct.

## Paged listings

`/api/documents/`, `/api/folders/`, `/api/collections/`, `/api/agents/`,
`/api/permissions/` and `/api/search/log/` answer with `count`, `next`,
`previous` and `results`. `PAGE_SIZE` sets the default and `MAX_PAGE_SIZE` the
ceiling a caller may ask for with `?page_size=`. The panel follows the `next`
links until it has the whole listing, because it draws a tree and a folder
rather than a page.

## What agents searched for

Every search is recorded, through either door: which agent asked, what it
asked, whether it was narrowed to a folder, how many passages came back, how
long it took and whether it failed. A search that returned nothing is recorded
too, since a run of empty answers is usually the first sign that a permission
is missing rather than that the store is empty.

```sh
curl -b cookies.txt "https://your.host/api/search/log/?agent=<id>"
```

The log is the owner's. An agent that could read it would learn what every
other agent was asked to look into.

## Embedding models

A collection names the model that produced its vectors. `local` runs a
sentence-transformers model inside the container and needs no account
anywhere; `api` points at any endpoint that speaks the OpenAI embeddings
shape, which covers most hosted providers as well as a model you run yourself.
Registering one is done in the panel, under Collections.

Vectors of two models cannot be compared, so a model belongs to one collection
and one only. Registering a model a collection already holds is refused, in the
serializer and on the table, and the refusal names the collection that has it.

### Registering one without knowing its details

The form asks for an endpoint, a model name and a vector width, and until you
have used a provider before you know none of the three. So it asks the
endpoint instead:

1. Pick a provider, which fills in its base URL. Anything else that speaks the
   same shape is typed in; the list only saves keystrokes.
2. Paste the key. **List the models** reads them from the endpoint itself, so a
   model the provider added today is offered today, and a mistyped URL or a
   rejected key fails here rather than on a document three hours later. An
   endpoint serving a single model has no list to give and says so; type the
   name.

   Only the embedding models are listed. A provider serves a handful of them
   beside a long list of chat models and rerankers, and one of those picked by
   mistake registers a collection that can never index anything — a mistake
   found only once a document has been uploaded, switched on and put through
   the queue. Each catalogue entry says how its provider names them
   (`embedding_pattern`), because not every embedding model has the word in its
   name: Voyage calls its models `voyage-3.5`. The form says how many it left
   out and offers to show them, and a list where nothing is recognisable is
   shown whole, since an empty list is worse than the mistake being prevented.
3. **Measure the width** embeds one sentence and fills the width in from what
   came back. It is the one field nobody can guess and the one that makes every
   stored vector unusable when it is wrong.

The list of providers is `backend/apps/ingestion/providers.json`, or whatever
`PROVIDER_CATALOGUE` points at. It is data, not code: nothing in this project
is written for one company, and an entry there only saves typing a URL.

### Where the credential lives

Set `CREDENTIALS_ENCRYPTION_KEY` and the panel keeps each collection's key,
encrypted in its row with Fernet. It is written once and never shown again;
the API says only whether one is held. Generate the key with:

```sh
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Changing that key makes every stored credential unreadable, which reads as no
credential at all rather than as a crash, so rotating it means re-entering the
keys in the panel.

A row in a database is still a row somebody may be able to read, so the
environment works exactly as before and wins when nothing is stored:
`EMBEDDING_API_KEY_<NAME>` — the collection name upper cased with hyphens
turned into underscores, so `openai-large` reads
`EMBEDDING_API_KEY_OPENAI_LARGE` — and `EMBEDDING_API_KEY` as the shared
fallback. Leave `CREDENTIALS_ENCRYPTION_KEY` empty to keep it that way: the
panel then refuses to store a credential and says why. Order of precedence:
the stored key, then the one named after the collection, then the shared one.

### Which model indexes which folder

| Folder | Model |
| --- | --- |
| The root | The base model of the instance, chosen under Collections |
| Directly under the root | Chosen when the folder is created |
| Anywhere deeper | Inherited from its parent, and not offered as a choice |

A folder keeps the model it was created with. Inheriting only at creation is
what keeps one branch searchable as one thing: a subtree split across two
models could not be ranked against itself.

Changing the base model re-indexes the documents sitting directly in the root,
because what they had indexed belonged to the model they are leaving. Folders
below the root are untouched, so a branch never changes model under its own
documents. Moving one document into a folder on another model has the same
cost, and the panel says so before it happens.

## The panel

Everything below is done by the owner, signed in with a session; agents never
reach any of it.

| Screen | What it does |
| --- | --- |
| Documents | The folder tree, uploads, renaming, moving and deleting, and the switch that makes a document readable by agents |
| Agents | Registering agents, issuing and revoking tokens, and jumping to what one of them can reach |
| Permissions | Granting and blocking one agent over one folder, with the resolved tree beside the rules |
| Collections | Registering embedding models, choosing the base one, and seeing which folders use each |
| Status | Whether PostgreSQL, Redis, Qdrant and the object storage answer |

A token is shown once, when it is issued, and never again. Deleting a folder
takes everything below it, deleting a document takes its file, and revoking a
token takes effect on the next call: each of those asks first and says what is
about to be lost. A form with something typed into it warns before a reload or
a step backwards throws it away.

The panel is translated, and the language is chosen in the header. Both
locales are complete; a key present in one and missing from the other is a bug.

## Running behind a reverse proxy

Set `PUBLIC_HOST` in `.env` to the hostname the browser will use:

```
PUBLIC_HOST=rag.example.com
TRUSTED_PROXY_COUNT=1
```

`PUBLIC_HOST` adds the host to Django's `ALLOWED_HOSTS`, trusts
`https://<host>` for CSRF, honours the `X-Forwarded-Proto` header, and tells
the Vite dev server to accept the host and to open its hot reload socket
through the proxy.

`TRUSTED_PROXY_COUNT` must match how many proxies you put in front — one for
the virtual host below. Left at its default of `0`, rate limiting counts the
proxy's own address instead of the caller's, so every caller shares one
allowance and any of them can exhaust the login limit for everyone.

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

## Connecting an agent over MCP

The server speaks the Model Context Protocol over HTTP at `/mcp/`, and
authenticates with the same bearer token an agent uses for the search
endpoint. Issue one in the panel, under Agents, and grant the agent the
folders it should read; a token that has been granted nothing can connect and
will find nothing.

The panel writes the configuration for you. It appears where the token does,
at the moment one is issued, which is the only moment the token exists in
readable form — the command, the configuration file and a curl to check it
with, each with a copy button. **Connect** on an agent's card shows the same
three afterwards, with a placeholder where the token goes.

The address comes from the request rather than from a setting, so an instance
behind a proxy reports the address its agents can actually reach.

Point a client at the endpoint with the token in an `Authorization` header:

```sh
claude mcp add --transport http ragmanager https://your-host.example/mcp/ \
  --header "Authorization: Bearer rmg_your_token_here"
```

```json
{
  "mcpServers": {
    "ragmanager": {
      "type": "http",
      "url": "https://your-host.example/mcp/",
      "headers": {
        "Authorization": "Bearer rmg_your_token_here"
      }
    }
  }
}
```

### Connecting claude.ai

Claude Code and Claude Desktop take a token in a header. claude.ai has no such
field: it connects through OAuth, so this server is one. Add a custom connector
pointing at `https://your-host.example/mcp/` and the rest happens in a browser:

1. It reads `/.well-known/oauth-protected-resource`, which the MCP endpoint
   names in the `WWW-Authenticate` header of its refusal, and follows it to
   this instance's authorization server.
2. It registers itself, which grants it nothing at all.
3. You are sent to an approval screen, signing in first if you are not already.
   It asks **which agent the connector acts as**: the connector then reads
   exactly what that agent was granted, and the permissions, the record of what
   was searched and the rate limit all work as they always did, because what it
   ends up holding is an ordinary agent token.
4. Approving hands it a token that expires in an hour and a renewal it uses on
   its own.

A connector's token appears on the agent's card with every other token, and
revoking it there withdraws the renewal with it, which stops the connector
rather than pausing it for an hour.

The flow is OAuth 2.1: the proof key is required and only `S256` is accepted,
redirect addresses are matched exactly against the ones registered, an
authorization code is good once and for two minutes, and a renewal is rotated
on use. A code or a renewal that turns up twice is taken as a copy in somebody
else's hands, and everything descended from it is withdrawn rather than
guessing which of the two callers was the real one. Tokens are bound to this
MCP endpoint and refused anywhere else.

This needs the instance to be reachable over the public internet on https,
since the approval happens in the user's browser and the callback goes back to
the client.

Three tools are offered:

| Tool | What it does |
| --- | --- |
| `search_documents` | Searches everything the agent may read and returns the matching passages, text included. |
| `search_in_folder` | The same, restricted to one folder and everything below it. |
| `list_readable_folders` | Lists the folders the agent may read, so a search can be narrowed to one. |

A folder the agent may not read and a folder that does not exist answer
identically, so an agent cannot map the tree by probing it.

Calls that embed a query are metered by the `SEARCH_THROTTLE_RATE` rate; the
handshake and the tool listing are not, so an agent never spends its allowance
on connecting.

The endpoint, the two `.well-known` documents and the registration and token
endpoints answer a browser from any origin, so a client of the transport that
runs inside one, such as the MCP Inspector, can connect and authorize. Nothing
there acts on a cookie; the panel's API and the approval screen stay closed to
every origin but the panel's own.

The endpoint answers each call in the reply to that call, in JSON, and keeps no
session between calls. It opens no listening stream, which a client discovers
by being refused on `GET`, and reconnecting costs nothing because there is no
state to restore.

## Health report

`GET /health/` probes PostgreSQL, Redis, Qdrant and the object storage bucket.
It answers `200` when every service is reachable and `503` as soon as one is
not, naming the one that failed. The reason a probe failed is added only for a
signed in owner, since driver errors quote hosts, users and endpoints. The web
panel renders the same report on its front page.

## Tests

```sh
docker compose exec backend python manage.py test apps
```

It also covers what happens to a stored credential on its way into a row and
back out, and what the panel does with an endpoint that cannot be reached, one
that refuses the key and one that serves a single model and has no list to
give.

The suite covers the permission resolver and the pieces that turn a resolved
permission into an answer, which is where a mistake would hand an agent a
document it was never granted. It also covers the MCP transport, the rules
about which folder may choose which embedding model, what deleting a folder
takes with it, how text is split, and which failures the queue tries again.
It touches only PostgreSQL, so it runs in seconds and needs no vector store,
object store or embedding model.

### Against a real provider

The API provider is otherwise tested against a stub, which proves this code
does what the project believes the protocol to be and nothing about whether
that belief is right. Point these at any OpenAI compatible embeddings endpoint
to check it against a service that actually implements it:

```sh
docker compose exec \
  -e LIVE_EMBEDDING_BASE_URL=http://your-endpoint/v1 \
  -e LIVE_EMBEDDING_MODEL=<the model to ask for> \
  -e LIVE_EMBEDDING_VECTOR_SIZE=<its width> \
  -e LIVE_EMBEDDING_API_KEY=<a key, if it wants one> \
  backend python manage.py test apps.ingestion.test_live
```

They are skipped when nothing is configured. Worth knowing, because these
tests found it: an endpoint serving a single model ignores the model name and
answers with the model it has, so a collection can be registered under a name
nobody serves and still work. The width check is what catches that.

There are no tests in front of the panel yet. Its types are checked, and the
two locales are compared for keys that exist in one and not the other:

```sh
cd frontend && npx vue-tsc --noEmit
```

## Project layout

```
backend/            Django project
  config/           settings, routing, Celery application, health probes
  apps/accounts/    the owner and the session they sign in with
  apps/agents/      agents, their tokens and the bearer authentication
  apps/drive/       collections, folders, documents and the storage behind them
  apps/access/      permission rules and the resolver that reads them
  apps/ingestion/   extraction, chunking, embeddings and the Qdrant client
  apps/search/      one query against every collection an agent may read
  apps/common/      the few helpers more than one app needs: paging, fields
  apps/mcp/         the MCP endpoint: JSON-RPC envelope, tools, transport
  apps/oauth/       the authorization flow a connector goes through
frontend/           Vue 3 single page application
  public/              the logo, drawn as SVG, and the icons derived from it
  src/components/ui/   the pieces every screen is built from
  src/composables/     behaviour shared between screens
  src/stores/          Pinia stores, one per area of the panel
docker-compose.yml  postgres, redis, minio, backend, worker, frontend
```

The backend image carries a single application build with two entry points,
`web` and `worker`, because the embedding model is needed both to ingest
documents and to vectorise incoming agent queries.

## Licence

MIT. See [LICENSE](LICENSE).
