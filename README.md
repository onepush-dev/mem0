# Mem0 — self-hosted AI memory API + dashboard (v2.2.1, pgvector). Deploy on Railway with one click.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/nsYLdD)

[Mem0](https://mem0.ai) is the open-source memory layer for AI agents: send it conversation turns, it extracts durable facts with an LLM, stores them as embeddings in Postgres/pgvector and returns the relevant ones per `user_id`, `agent_id` or `run_id`. This template runs the **official self-hosted stack from the v2.2.1 release** (FastAPI REST server + Next.js dashboard) on **Railway Postgres (pgvector)**, behind **one public domain**, with **zero deploy-time inputs**. The LLM key is optional and can be added after deploy.

## Why this template
- **Current and pinned:** upstream `mem0ai/mem0` **v2.2.1** (commit `94c3fe9f238f3dbf29c9ce98643bd71eb13077cd`, tarball sha256-verified) with `mem0ai==2.2.1` and a full pip constraints lock. Base images are pinned by digest. Nothing uses `latest`.
- **Runs on Railway's amd64 hosts:** the only official image (`mem0/mem0-api-server:latest`) is arm64-only and dates from Sept 2025. This repo's GitHub Actions workflow builds `ghcr.io/onepush-dev/mem0-api` and `ghcr.io/onepush-dev/mem0-dashboard` from the Dockerfiles here. The template deploys those images by digest, so there is no build step at deploy time.
- **Boots without an LLM key:** upstream builds the OpenAI client at import time and crash-loops with `Missing credentials` if no key is set. Every other Mem0 template on Railway therefore makes you paste an OpenAI key before you can deploy. Here, a small build-time patch (`api/patch_upstream.py`) makes that one step lazy. The API, auth, API keys and dashboard come up healthy, and memory endpoints answer a clear `provider_not_configured` error until you add a key. After that they work with no rebuild.
- **One public domain:** a Caddy proxy (`mem0`) is the only public service. It sends API paths (`/memories`, `/search`, `/auth`, `/api-keys`, `/docs`, …) to `mem0-api` and everything else to `mem0-dashboard`. The dashboard and API share an origin, so there is no CORS setup and the refresh cookie is `Secure`. The API, dashboard and Postgres stay on private networking.
- **Upstream gaps fixed:** the `mem0_app` database is created automatically (upstream uses an init script Railway Postgres can't mount), `alembic upgrade head` runs on every boot, `uvicorn --reload` is gone, and the API listens dual-stack on `[::]` for Railway's IPv6 private network and the healthcheck.
- **Everything persistent is on a volume:** Postgres data (memories, users, API keys, settings, request log) and the API's SQLite memory-history DB at `/app/history`. Telemetry is off.

## Services
| Service | Source | Notes |
|---|---|---|
| mem0 | image `caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f` | **only public domain**, port `8080`, health `/healthz`, Caddyfile from the `CADDYFILE` variable (`proxy/Caddyfile`) |
| mem0-api | image `ghcr.io/onepush-dev/mem0-api:v2.2.1@sha256:b43ca243fffdbb8112992b87eb32da39a2e28de2491198a9f72827fe24f8ff91` (built from `api/`) | port `8000`, private, volume `/app/history`, health `/docs`, image CMD `python /railway/railway_start.py` |
| mem0-dashboard | image `ghcr.io/onepush-dev/mem0-dashboard:v2.2.1@sha256:9e654f2351b8177296146aab1ba28aa27159b2f54f012762a57c8d59d0c58e82` (built from `dashboard/`) | port `3000`, private, health `/api/health`, upstream entrypoint + `node server.js` |
| Postgres | Railway Postgres (`ghcr.io/railwayapp-templates/postgres-ssl:18`, pgvector 0.8 included) | volume `/var/lib/postgresql/data`. Databases: `railway` (pgvector `memories`) + `mem0_app` (users, keys, settings, logs) |

**Proxy start command** (writes `CADDYFILE`, then runs Caddy):
```
sh -c 'printf "%s\n" "$CADDYFILE" > /etc/caddy/Caddyfile && exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile'
```
(Also in `proxy/start-command.txt`.) The API and dashboard need no start command. Their image CMD/ENTRYPOINT already does the work.

**What the API does at start** (`api/railway_start.py`): it waits for Postgres, runs `CREATE EXTENSION IF NOT EXISTS vector`, creates `APP_DB_NAME` if it is missing, runs `alembic upgrade head`, then starts uvicorn on a dual-stack `[::]:$PORT` socket with proxy headers on.

## Variables
### mem0-api
| Variable | Template value | Secret |
|---|---|---|
| PORT | `8000` | |
| POSTGRES_HOST | `${{Postgres.PGHOST}}` | |
| POSTGRES_PORT | `${{Postgres.PGPORT}}` | |
| POSTGRES_USER | `${{Postgres.PGUSER}}` | |
| POSTGRES_PASSWORD | `${{Postgres.PGPASSWORD}}` | yes (reference) |
| POSTGRES_DB | `${{Postgres.PGDATABASE}}` | |
| POSTGRES_COLLECTION_NAME | `memories` | |
| APP_DB_NAME | `mem0_app` (created on first boot) | |
| HISTORY_DB_PATH | `/app/history/history.db` | |
| MEM0_DIR | `/app/history/.mem0` | |
| MEM0_TELEMETRY | `false` | |
| AUTH_DISABLED | `false` | |
| JWT_SECRET | `${{secret(64, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")}}`. Signs dashboard sessions. Changing it logs everyone out. | yes |
| ADMIN_API_KEY | `${{secret(48, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")}}`. Server-wide admin key, sent as `X-API-Key`. | yes |
| DASHBOARD_URL | `https://${{mem0.RAILWAY_PUBLIC_DOMAIN}}` (CORS origin) | |
| MEM0_DEFAULT_LLM_MODEL | `gpt-5-mini` | |
| MEM0_DEFAULT_EMBEDDER_MODEL | `text-embedding-3-small` | |
| OPENAI_API_KEY | empty, set after deploy | yes (when set) |
| OPENAI_BASE_URL | empty (any OpenAI-compatible endpoint, e.g. OpenRouter or LiteLLM) | |

### mem0-dashboard
| Variable | Template value |
|---|---|
| PORT | `3000` |
| HOSTNAME | `::` |
| NEXT_PUBLIC_API_URL | `https://${{mem0.RAILWAY_PUBLIC_DOMAIN}}` (same origin, through the proxy) |
| NEXT_PUBLIC_INSTANCE_NAME | `Mem0` |
| API_INTERNAL_URL | `http://${{mem0-api.RAILWAY_PRIVATE_DOMAIN}}:${{mem0-api.PORT}}` |
| DASHBOARD_URL | `https://${{mem0.RAILWAY_PUBLIC_DOMAIN}}` (makes the refresh cookie `Secure`) |

### mem0 (proxy)
| Variable | Template value |
|---|---|
| PORT | `8080` |
| MEM0_API_UPSTREAM | `${{mem0-api.RAILWAY_PRIVATE_DOMAIN}}:${{mem0-api.PORT}}` |
| MEM0_DASHBOARD_UPSTREAM | `${{mem0-dashboard.RAILWAY_PRIVATE_DOMAIN}}:${{mem0-dashboard.PORT}}` |
| CADDYFILE | contents of `proxy/Caddyfile` |

### Postgres
Railway Postgres defaults: `POSTGRES_USER=postgres`, `POSTGRES_DB=railway`, `POSTGRES_PASSWORD=${{secret(32, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")}}` (keep it alphanumeric, because the API builds its SQLAlchemy URL from it unescaped), `PGDATA=/var/lib/postgresql/data/pgdata`, plus the usual `PG*`/`DATABASE_URL` aliases.

## After deploy
1. Open `https://<your-domain>` **right away**. It redirects to the setup wizard, and the first account you create becomes the admin. Registration then closes (`403 Registration is closed`).
2. Add a model key: set `OPENAI_API_KEY` on **mem0-api** (Railway redeploys it), or enter a provider and key on the dashboard **Configuration** page. Anthropic and Gemini LLMs are bundled, and embeddings need OpenAI or Gemini. For an OpenAI-compatible gateway, set `OPENAI_BASE_URL` too.
3. Create per-app keys under **API Keys** (`m0sk_…`), or use `ADMIN_API_KEY` from the mem0-api Variables tab.
4. Store and search memories:
   ```bash
   curl -X POST https://<your-domain>/memories -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"I prefer dark roast coffee"}],"user_id":"alice"}'
   curl -X POST https://<your-domain>/search -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"query":"what coffee does alice like?","filters":{"user_id":"alice"}}'
   ```
   Interactive API docs are at `https://<your-domain>/docs`. Other Railway services can call `http://${{mem0-api.RAILWAY_PRIVATE_DOMAIN}}:8000` privately.

Health (no auth): `GET /healthz` → `ok` (proxy), `GET /docs` → `200` (API), `GET /api/health` → `{"status":"ok"}` (dashboard).

**Before a key is set**, memory endpoints (`/memories`, `/search`, `/entities`, …) return `502` with:
```json
{"detail":"No LLM/embedding provider is configured yet. Set OPENAI_API_KEY on the mem0-api service (or pick a provider and key on the dashboard Configuration page), then retry.","code":"provider_not_configured"}
```
Auth, setup, API keys, the request log and `/docs` work from the first boot. If the key is wrong, you get upstream's `provider_auth_failed`.

## Notes
- Template editor (unpublished): https://railway.com/workspace/templates/be3979b2-8ea8-4e94-960c-191a8190a410
- Live source project: https://railway.com/project/339dfd8e-e6bf-4dd7-9fc2-76f3453d73e8 (template editor URL added after generation).
- Run **one replica** of `mem0-api`, because memory history is SQLite on its volume. The dashboard is stateless.
- Settings saved on the dashboard Configuration page are stored in Postgres and **override** env variables. If you entered a key there, change it there.
- Changing the embedding model or its dimensions after memories exist needs a new `POSTGRES_COLLECTION_NAME`.
- `request_logs` grows with traffic. Upstream ships `scripts/prune_request_logs.py`, which you can run inside the API container.
- Dashboard entries marked PRO (analytics, webhooks, export) belong to Mem0's commercial platform and do nothing in the OSS server.
- Upgrading: bump `MEM0_COMMIT`/`MEM0_TARBALL_SHA256` in both Dockerfiles (and `mem0ai==` / `constraints.txt` in `api/`). CI publishes new images, and you then point the services at the new digests. Back up Postgres and the `/app/history` volume first.
- OpenMemory (the old MCP server + UI) was removed upstream and its images are stale (June 2025), so this template ships the maintained REST server. Mem0 v2 removed the graph store (Neo4j) from the library, so no Neo4j service is needed.
- Upstream: https://github.com/mem0ai/mem0 · Server docs: https://docs.mem0.ai/open-source/features/rest-api · Release: https://github.com/mem0ai/mem0/releases/tag/v2.2.1
