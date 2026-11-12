# Core API image and Managed Redis configuration

Runbook for [EFC-293](https://linear.app/jayhsia/issue/EFC-293) under the [Azure deployment plan](azure-deployment.md) and [ADR 0039](adr/0039-azure-deployment-and-release-direction.md).

Execution boundary: agents author code, scripts, docs, and offline/local tests only. Every Azure account or resource operation is performed by a human operator. Nothing here has been verified against Azure.

| Verification                                     | Who      | Status                                                      |
| ------------------------------------------------ | -------- | ----------------------------------------------------------- |
| Local image build and smoke (disposable TLS PostgreSQL 18 + Redis 7.4) | Agent | Passed 2026-11-12, local build `sha256:882a436d83cff9c9fa95c2ecae12f6325c7e78c186bae4f9b7e3d04af12a83c5` |
| Offline pytest (Redis client, per-client limiter keys, mounted-app limiting, auth state TTL) | Agent | Passed 2026-11-12 |
| Real Azure PostgreSQL / Managed Redis / App Service checks | Human operator | **Pending** — see [Operator tests on Azure](#operator-tests-on-azure-human) |

Local results do not prove Azure Managed Redis or Azure PostgreSQL compatibility.

## What the image and configuration now do

- **Startup:** `entrypoint.sh` runs `gunicorn -c gunicorn_conf.py portal:app` with gunicorn's native ASGI worker, bound to `0.0.0.0:8000`, lifespan required (`asgi_lifespan = "on"`). Lifespan starts the Redis rate limiters and the Pending-payment expiry sweep, and SIGTERM shuts both down before exit code 0.
- **Build context:** `.dockerignore` is an allowlist. Only `pyproject.toml`, `uv.lock`, `.python-version`, `gunicorn_conf.py`, `entrypoint.sh`, `env/rate_limiters.yaml`, and `portal/` enter the image. `.env`, `.envrc`, `.git`, tests, docs, `mock-seed/`, `alembic/`, and editor/agent folders stay out. The image runs as non-root `appuser`.
- **Redis database 0:** every Redis client uses the database in `REDIS_URL` (no path means 0). `REDIS_DB`, `RATE_LIMITER_REDIS_DB` (previously db 10), and `TOKEN_BLACKLIST_REDIS_DB` are removed; setting them has no effect.
- **Key/state separation in one database:** all keys share the `newlife-core-api:` prefix.

  | State                       | Key pattern                                           | Expiry                              |
  | --------------------------- | ----------------------------------------------------- | ----------------------------------- |
  | Rate limiter (per client)   | `newlife-core-api:rate_limiter:<default\|read\|write>:<ip>:<path>` | Longest window (default 1 h); older entries trimmed on each request |
  | Access-token revocation     | `newlife-core-api:token_blacklist:<sha256>`           | Remaining access-token lifetime     |
  | Member refresh app binding  | `newlife-core-api:member_refresh_app:<family_id>`     | `REFRESH_TOKEN_EXPIRE_DAYS`         |
  | Caches (locale, permission, role, verb, setting, file) | `newlife-core-api:<resource>:…`  | Per cache (`CacheExpiry`)           |

  Old rate limiter keys (`newlife-core-api_limiter_*` in db 10) are abandoned; they had no effect (see below).
- **Client and TLS:** `rediss://` enables TLS with certificate and hostname verification. Clients retry connection errors and timeouts 3 times with jittered exponential backoff (0.5 s base, 5 s cap), health-check idle connections every 30 s, and use TCP keepalive.
- **Rate limiting works with Redis, per client:** `/admin` and `/api` are mounted sub-apps, and Redis limiters were set only on the root app, so with `REDIS_URL` set, rate limiting was silently off. Lifespan now attaches limiters to mounted apps. Each client identifier (first `X-Forwarded-For` address, else the peer address, plus the request path) has its own sorted set, and one atomic script checks the short/medium/long windows from `env/rate_limiters.yaml` (default: 10/s, 50/30 s, 1000/h per client and path). The previous pyrate-limiter buckets were one shared bucket per window for all clients.
- **Failover/restart:** the Redis script cache is neither persisted nor replicated. The limiter script is registered through redis-py, which reloads it on `NOSCRIPT`; the plain pyrate-limiter bucket failed every rate-limited request until the app restarted.
- **Config import:** an unset `CORS_ALLOWED_ORIGINS` no longer crashes startup; the default applies.
- **PostgreSQL TLS:** no code change. asyncpg (app) and libpq/psycopg2 (Alembic) both read `PGSSLMODE` and `PGSSLROOTCERT`. asyncpg needs an explicit root certificate file for `verify-full`; the image's system bundle is `/etc/ssl/certs/ca-certificates.crt`.
- **PostgreSQL version:** migrations use `uuidv7()`, which needs **PostgreSQL 18**. Provision Flexible Server version 18.

## Build, run, stop (local)

```bash
# Build
docker build -t newlife-core-api:local .
docker image inspect -f '{{.Id}}' newlife-core-api:local

# Full local smoke: builds, starts disposable TLS-only PostgreSQL 18 and Redis 7.4, migrates/seeds them,
# runs the image, checks it, stops it, and removes everything. Never contacts Azure.
scripts/local-image-smoke.sh newlife-core-api:local
#   SMOKE_SKIP_BUILD=1  reuse the tag     SMOKE_API_PORT=8000  host port     SMOKE_KEEP=1  keep containers

# Run against your own throwaway services (never production credentials)
docker run -d --name core-api -p 127.0.0.1:8000:8000 --env-file ./local-test.env newlife-core-api:local
curl -i http://127.0.0.1:8000/healthz
docker logs -f core-api
docker stop -t 30 core-api && docker rm core-api
```

The image contains no `.env`, so anything unset falls back to code defaults. `local-test.env` for the `docker compose` services (Postgres on host port 5434, Redis on 6380, migrated and seeded as in the README); plain TCP, because those services have no TLS (the smoke script covers TLS):

```dotenv
ENV=dev
SENTRY_ENABLED=false
DATABASE_HOST=host.docker.internal
DATABASE_PORT=5434
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=postgres
REDIS_URL=redis://host.docker.internal:6380/0
JWT_SECRET_KEY=local-only-change-me-0123456789abcdef
REFRESH_TOKEN_HASH_SALT=local-only-salt
REFRESH_TOKEN_HASH_PEPPER=local-only-pepper
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174
```

Expected smoke output (2026-11-12):

```text
    PASS no local secrets, Git metadata, or dev-only files; non-root user
    PASS PostgreSQL (hostssl only) and Redis (TLS port only) ready
    PASS schema migrated; locales, RBAC, and smoke superuser seeded
    PASS GET /healthz -> 200 via host port 8000 -> container 8000
    PASS listening on 0.0.0.0:8000; rate limiters on TLS Redis; expiry sweep running
    PASS login 200, me 200, refresh 200, logout 200, revoked refresh token 401
    PASS db0:keys=11,expires=11,…; all keys under newlife-core-api:; revocation TTL 898s
    PASS first request after restart -> 200 (reconnected; rate-limit script reloaded)
    PASS one client's burst of 40 ->   12 200   28 429 ; another client -> 200; limiter key expires in 3599852ms
    PASS SIGTERM -> lifespan finished, exit code 0
SMOKE PASSED  image=newlife-core-api:local id=sha256:…
```

### Tests

```bash
uv run pytest tests/libs/database/test_aio_redis.py tests/libs/depends/test_rate_limiters.py \
  tests/providers/test_redis_state_providers.py tests/test_config.py -v

# Real Redis, database 0 (use a throwaway instance, not your dev Redis)
docker run -d --rm --name redis-db0 -p 6391:6379 redis:7.4-alpine
PORTAL_REDIS_INTEGRATION=1 REDIS_URL=redis://localhost:6391/0 uv run pytest tests/integration/test_redis_db0.py -v
docker stop redis-db0
```

## App Service settings

Settings this ticket depends on. Others (Microsoft Entra, Blob, mail, Sentry) follow `example.env` and the deployment plan. Secrets use Key Vault references, never plain values in Git.

| Setting                     | Value                                                                 | Notes |
| --------------------------- | --------------------------------------------------------------------- | ----- |
| `WEBSITES_PORT`             | `8000`                                                                | Container listens on 8000 only (non-root cannot bind 80). |
| Always On (General settings)| On                                                                    | Keeps the worker and the Pending-payment expiry sweep alive. |
| `ENV`                       | `stg` / `prod`                                                        | |
| `DATABASE_HOST`             | `<server>.postgres.database.azure.com`                                | |
| `DATABASE_PORT`             | `5432`                                                                | |
| `DATABASE_USER` / `DATABASE_PASSWORD` / `DATABASE_NAME` | per server                                | Password via Key Vault. |
| `PGSSLMODE`                 | `verify-full`                                                         | |
| `PGSSLROOTCERT`             | `/etc/ssl/certs/ca-certificates.crt`                                  | Image system bundle; Azure server certificates chain to public roots. |
| `REDIS_URL`                 | `rediss://:<access-key>@<name>.<region>.redis.azure.net:10000/0`      | Key Vault. Percent-encode the key if it contains `/`, `+`, `=`, `@`, or `:`. Path must be `/0` or empty. No `ssl_ca_certs` (public CA). |
| `JWT_SECRET_KEY`            | random, ≥ 32 bytes                                                    | Key Vault. |
| `REFRESH_TOKEN_HASH_SALT` / `REFRESH_TOKEN_HASH_PEPPER` | random                                    | Key Vault. |
| `CORS_ALLOWED_ORIGINS`      | comma-separated Portal and Facility Booking origins                   | Always set. Unset falls back to the code default `*` (credentials allowed). |
| `WEB_CONCURRENCY`           | `1` (default)                                                         | Each worker runs its own expiry loop; the PostgreSQL advisory lock serialises sweeps. |
| `FORWARDED_ALLOW_IPS`       | unset                                                                 | Rate limiting reads `X-Forwarded-For` directly. |

Managed Redis: access-key authentication (the app has no Entra token support for Redis), TLS port 10000, and a **non-clustered** policy if the SKU offers it, otherwise **Enterprise**. Do not use the **OSS cluster** policy: the app uses a non-cluster client.

## Operator tests on Azure (human)

Run per environment, staging first. Record results with the template at the end. Do not paste keys, passwords, or tokens.

1. **PostgreSQL TLS** — from an allowlisted operator IP:
   `psql "host=<server>.postgres.database.azure.com port=5432 dbname=<db> user=<user> sslmode=verify-full sslrootcert=system" -c 'select version();'`
   Expect `PostgreSQL 18.x`. Retry with `sslmode=disable`; expect rejection. After deploying, App Service logs show no `SSL` or `ClientConfigurationError` errors.
2. **Redis TLS and database 0** —
   `redis-cli --tls -h <name>.<region>.redis.azure.net -p 10000 -a '<access-key>' --no-auth-warning PING` → `PONG`.
   `… SELECT 1` → error (single database). `… INFO keyspace` after app traffic → only `db0`. `… --scan --count 1000 | grep -v '^newlife-core-api:'` → empty.
3. **Policy compatibility** — confirm the policy in the portal (non-clustered or Enterprise). `… EVAL "return 1" 0` → `1`. Burst 40 parallel authenticated requests to `/admin/api/v1/auth/me` from one machine; expect some `429`, no `500`, while another machine still gets `200`. Under Enterprise policy, also edit a locale in the Portal (runs the multi-key `DEL` in `LocaleCache.clear`) and confirm no `CROSSSLOT` error in logs.
4. **Port, startup, Always On** — with `WEBSITES_PORT=8000` and Always On set, restart the app. Log stream shows `Listening at: http://0.0.0.0:8000`, `Redis rate limiters initialized`, `Pending-payment expiry sweep started`, and no `Failed to initialize Redis rate limiters`. `curl -i https://<app-host>/healthz` → `200`. After 30+ minutes without traffic, logs still show sweep activity and no cold start.
5. **Authentication** — Portal sign-in, token refresh, logout. After logout, the old refresh token is rejected (`401`).
6. **Restart / failover / reconnect** — use the restart, maintenance, or failover operation the selected SKU offers (production HA; staging has none). During and right after: requests may fail briefly, then recover without an app restart; no repeating `ConnectionError` or `NoScriptError` in logs; the first rate-limited request after recovery returns `200`; `redis-cli … INFO memory` shows `number_of_cached_scripts` ≥ 1 again.
7. **App restart** — restart App Service; confirm a brief interruption only (Basic has no slots), then checks 4–5 pass.

Evidence template (reply on the ticket):

```text
Operator: <name>   Date/time (UTC): <…>   Environment: staging | production
Image: <tag> @ <digest>   App: <app name>   Redis: <name, SKU, policy, HA>   PostgreSQL: <name, version>
1 PG TLS: pass/fail <notes>     2 Redis TLS/db0: pass/fail     3 Policy: pass/fail
4 Port/Always On: pass/fail     5 Auth: pass/fail              6 Failover/reconnect: pass/fail/not run
7 App restart: pass/fail        Cleanup: <…>
```

## Known limitations (not changed here)

- **Access tokens survive logout until they expire** (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 15). Logout writes the revocation key, but no request path reads `is_blacklisted`. Refresh tokens are revoked.
- **The client IP comes from the first `X-Forwarded-For` entry,** which a client can set. A caller can spread requests across forged addresses. Confirm what App Service puts in that header before relying on limits for abuse protection. The path in the identifier includes IDs, so each `/…/{id}` path counts separately.
- **`/healthz` touches Redis** through the locale middleware and returns `500` while Redis is unreachable. An App Service health check on `/healthz` therefore also tracks Redis.
- **Redis unavailable at startup** disables Redis rate limiting (fail-open) until the app restarts; the log shows `Failed to initialize Redis rate limiters`.
- The image keeps its build toolchain (`build-base`, `libffi-dev`), which adds size.
