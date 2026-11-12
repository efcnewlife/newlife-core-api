#!/usr/bin/env bash
# Build the Core API image and smoke-test it against disposable, TLS-only local PostgreSQL and Redis.
#
# Local only: never contacts Azure or ACR. Proves image startup, port 8000, secret exclusion,
# database 0 Redis usage over TLS, login/refresh/logout, rate limiting, Redis restart recovery,
# and graceful shutdown. It does NOT prove Azure Managed Redis or Azure PostgreSQL compatibility.
#
# Usage: scripts/local-image-smoke.sh [image-tag]
#   SMOKE_SKIP_BUILD=1   reuse an existing image tag instead of building
#   SMOKE_API_PORT=8000  host port mapped to the container's 8000
#   SMOKE_KEEP=1         leave containers running for inspection (clean up with the printed command)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${1:-newlife-core-api:local}"
API_PORT="${SMOKE_API_PORT:-8000}"
PG_PORT=55432
REDIS_PORT=56379
PREFIX="newlife-smoke"
NET="$PREFIX-net"
PG="$PREFIX-pg"
REDIS="$PREFIX-redis"
API="$PREFIX-api"
WORK="$(mktemp -d)"
CERTS="$WORK/certs"

PG_PASSWORD="smoke-pg-$RANDOM$RANDOM"
REDIS_PASSWORD="smoke-redis-$RANDOM$RANDOM"
ADMIN_EMAIL="smoke-admin@example.com"
ADMIN_PASSWORD="smoke-pass-$RANDOM$RANDOM"
BASE="http://127.0.0.1:$API_PORT"

step() { printf '\n==> %s\n' "$*"; }
pass() { printf '    PASS %s\n' "$*"; }
fail() {
  printf '    FAIL %s\n' "$*" >&2
  docker logs --tail 80 "$API" 2>&1 | sed 's/^/    | /' >&2 || true
  exit 1
}

cleanup() {
  if [ "${SMOKE_KEEP:-0}" = "1" ]; then
    printf '\nKept. Clean up with: docker rm -f %s %s %s; docker network rm %s; rm -rf %s\n' "$API" "$PG" "$REDIS" "$NET" "$WORK"
    return
  fi
  docker rm -f "$API" "$PG" "$REDIS" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

json_get() { python3 -c 'import json,sys; d=json.load(sys.stdin)
for k in sys.argv[1].split("."): d=d[k]
print(d)' "$1"; }

redis_cli() { docker exec "$REDIS" redis-cli --tls --cacert /certs/ca.crt -a "$REDIS_PASSWORD" --no-auth-warning "$@"; }

wait_healthz() {
  for _ in $(seq 1 60); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/healthz")" = "200" ]; then return 0; fi
    if [ "$(docker inspect -f '{{.State.Running}}' "$API" 2>/dev/null)" != "true" ]; then return 1; fi
    sleep 1
  done
  return 1
}

# Host-side CLI (migrations and seeds) talks to the disposable services only. portal.config loads the
# repo .env for any unset variable, so every variable these commands use is set explicitly here.
host_env() {
  env ENV=dev SENTRY_ENABLED=false SENTRY_DSN= TELEMETRY_BACKEND= \
    DATABASE_HOST=localhost DATABASE_PORT="$PG_PORT" DATABASE_USER=postgres DATABASE_PASSWORD="$PG_PASSWORD" DATABASE_NAME=postgres \
    PGSSLMODE=verify-full PGSSLROOTCERT="$CERTS/ca.crt" \
    REDIS_URL="rediss://:$REDIS_PASSWORD@localhost:$REDIS_PORT/0?ssl_ca_certs=$CERTS/ca.crt" \
    "$@"
}

step "Throwaway CA and server certificate"
mkdir -p "$CERTS"
# Python 3.13+ verifies strictly (X509_STRICT): CA key usage, leaf SAN, and Authority Key Identifier are required.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=newlife-smoke-ca" -keyout "$CERTS/ca.key" -out "$CERTS/ca.crt" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj "/CN=localhost" -keyout "$CERTS/server.key" -out "$CERTS/server.csr" 2>/dev/null
printf 'basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nsubjectAltName=DNS:localhost,DNS:%s,DNS:%s,IP:127.0.0.1\n' "$PG" "$REDIS" >"$CERTS/san.ext"
openssl x509 -req -in "$CERTS/server.csr" -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial -days 1 -extfile "$CERTS/san.ext" -out "$CERTS/server.crt" 2>/dev/null
chmod 644 "$CERTS/server.key"
pass "certificates in $CERTS"

if [ "${SMOKE_SKIP_BUILD:-0}" != "1" ]; then
  step "Build $IMAGE"
  docker build -t "$IMAGE" "$ROOT"
fi
IMAGE_ID="$(docker image inspect -f '{{.Id}}' "$IMAGE")"
pass "image $IMAGE ($IMAGE_ID)"

step "Secret exclusion in the image"
forbidden="$(docker run --rm --entrypoint sh "$IMAGE" -c 'cd /app && for p in .env .envrc .git tests docs alembic mock-seed temp example .tmp .scratch .claude .cursor .agents .idea .vscode infra scripts; do [ -e "$p" ] && echo "$p"; done; find . -path ./.venv -prune -o -name ".env*" -print; true')" || fail "could not inspect image contents"
[ -z "$forbidden" ] || fail "image contains: $forbidden"
[ "$(docker run --rm --entrypoint id "$IMAGE" -u)" != "0" ] || fail "image runs as root"
pass "no local secrets, Git metadata, or dev-only files; non-root user"

step "Disposable TLS-only PostgreSQL and Redis"
docker rm -f "$API" "$PG" "$REDIS" >/dev/null 2>&1 || true
docker network rm "$NET" >/dev/null 2>&1 || true
docker network create "$NET" >/dev/null
printf 'local all all trust\nhostssl all all all scram-sha-256\n' >"$CERTS/pg_hba.conf"
docker run -d --name "$PG" --network "$NET" -p "127.0.0.1:$PG_PORT:5432" -e POSTGRES_PASSWORD="$PG_PASSWORD" -v "$CERTS:/certs:ro" \
  postgres:18-alpine sh -c 'cp /certs/server.crt /certs/server.key /certs/pg_hba.conf /tmp/ && chown postgres /tmp/server.* /tmp/pg_hba.conf && chmod 600 /tmp/server.key &&
    exec docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/tmp/server.crt -c ssl_key_file=/tmp/server.key -c hba_file=/tmp/pg_hba.conf' >/dev/null
docker run -d --name "$REDIS" --network "$NET" -p "127.0.0.1:$REDIS_PORT:6379" -v "$CERTS:/certs:ro" redis:7.4-alpine \
  redis-server --port 0 --tls-port 6379 --tls-cert-file /certs/server.crt --tls-key-file /certs/server.key --tls-ca-cert-file /certs/ca.crt \
  --tls-auth-clients no --requirepass "$REDIS_PASSWORD" --save "" --appendonly no >/dev/null
for _ in $(seq 1 30); do docker exec "$PG" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break; sleep 1; done
for _ in $(seq 1 30); do [ "$(redis_cli PING 2>/dev/null)" = "PONG" ] && break; sleep 1; done
[ "$(redis_cli PING)" = "PONG" ] || fail "Redis TLS not ready"
pass "PostgreSQL (hostssl only) and Redis (TLS port only) ready"

step "Migrate and seed the disposable database from this checkout (TLS verify-full)"
(cd "$ROOT" && host_env uv run alembic upgrade head >"$WORK/migrate.log" 2>&1) || { tail -40 "$WORK/migrate.log" >&2; fail "alembic upgrade head"; }
(cd "$ROOT" && host_env uv run python -m portal.cli.main init-locales >"$WORK/seed.log" 2>&1) || { tail -40 "$WORK/seed.log" >&2; fail "init-locales"; }
(cd "$ROOT" && host_env uv run python -m portal.cli.main init-rbac >>"$WORK/seed.log" 2>&1) || { tail -40 "$WORK/seed.log" >&2; fail "init-rbac"; }
printf '%s\n%s\n%s\nSmoke\nAdmin\n' "$ADMIN_EMAIL" "$ADMIN_PASSWORD" "$ADMIN_PASSWORD" |
  (cd "$ROOT" && host_env uv run python -m portal.cli.main create-superuser >>"$WORK/seed.log" 2>&1) || { tail -40 "$WORK/seed.log" >&2; fail "create-superuser"; }
pass "schema migrated; locales, RBAC, and smoke superuser seeded"

step "Run the image (database 0 Redis over TLS, PostgreSQL verify-full)"
cat >"$WORK/api.env" <<EOF
ENV=stg
SENTRY_ENABLED=false
DATABASE_HOST=$PG
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=$PG_PASSWORD
DATABASE_NAME=postgres
PGSSLMODE=verify-full
PGSSLROOTCERT=/certs/ca.crt
REDIS_URL=rediss://:$REDIS_PASSWORD@$REDIS:6379/0?ssl_ca_certs=/certs/ca.crt
JWT_SECRET_KEY=smoke-jwt-$RANDOM$RANDOM$RANDOM
REFRESH_TOKEN_HASH_SALT=smoke-salt-$RANDOM
REFRESH_TOKEN_HASH_PEPPER=smoke-pepper-$RANDOM
EOF
docker run -d --name "$API" --network "$NET" -p "127.0.0.1:$API_PORT:8000" --env-file "$WORK/api.env" -v "$CERTS:/certs:ro" "$IMAGE" >/dev/null
wait_healthz || fail "GET /healthz did not return 200"
pass "GET /healthz -> 200 via host port $API_PORT -> container 8000"
sleep 2
logs="$(docker logs "$API" 2>&1)"
grep -q "Listening at: http://0.0.0.0:8000" <<<"$logs" || fail "gunicorn is not listening on 0.0.0.0:8000"
grep -q "Redis rate limiters initialized" <<<"$logs" || fail "Redis rate limiters did not initialize"
grep -q "Pending-payment expiry sweep started" <<<"$logs" || fail "Pending-payment expiry sweep did not start"
! grep -q "Pending-payment hold expiry sweep failed" <<<"$logs" || fail "Pending-payment expiry sweep failed"
pass "listening on 0.0.0.0:8000; rate limiters on TLS Redis; expiry sweep running"

step "Authentication: login, me, refresh, logout, revoked refresh token"
login="$(curl -sf -X POST "$BASE/admin/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")" || fail "login"
access="$(json_get token.accessToken <<<"$login")"
refresh="$(json_get token.refreshToken <<<"$login")"
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $access" "$BASE/admin/api/v1/auth/me")" = "200" ] || fail "GET /auth/me"
refreshed="$(curl -sf -X POST "$BASE/admin/api/v1/auth/refresh" -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$refresh\"}")" || fail "refresh"
access="$(json_get accessToken <<<"$refreshed")"
refresh="$(json_get refreshToken <<<"$refreshed")"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/admin/api/v1/auth/logout" -H "Authorization: Bearer $access" -H 'Content-Type: application/json' \
  -d "{\"access_token\":\"$access\",\"refresh_token\":\"$refresh\"}")"
[ "$code" = "200" ] || fail "logout returned $code"
# Logout revokes the refresh-token family. The access token stays valid until it expires: the
# blacklist is written (checked below) but not read on requests; see docs/azure-core-api-image.md.
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/admin/api/v1/auth/refresh" -H 'Content-Type: application/json' -d "{\"refresh_token\":\"$refresh\"}")"
[ "$code" = "401" ] || fail "revoked refresh token returned $code, expected 401"
pass "login 200, me 200, refresh 200, logout 200, revoked refresh token 401"

step "Redis keyspace: database 0 only, app namespace only, TTL on revocations"
keyspace="$(redis_cli INFO keyspace | tr -d '\r' | grep '^db' || true)"
[ "$(cut -d: -f1 <<<"$keyspace")" = "db0" ] || fail "keys outside db0: $keyspace"
stray="$(redis_cli --scan | grep -v '^newlife-core-api:' || true)"
[ -z "$stray" ] || fail "keys outside the newlife-core-api: namespace: $stray"
blacklisted="$(redis_cli --scan --pattern 'newlife-core-api:token_blacklist:*' | head -1)"
[ -n "$blacklisted" ] || fail "no access-token revocation key"
ttl="$(redis_cli TTL "$blacklisted")"
[ "$ttl" -gt 0 ] || fail "revocation key has no TTL ($ttl)"
pass "$keyspace; all keys under newlife-core-api:; revocation TTL ${ttl}s"

step "Redis restart: connections drop and the script cache is lost"
login="$(curl -sf -X POST "$BASE/admin/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")" || fail "login before restart"
access="$(json_get token.accessToken <<<"$login")"
docker restart "$REDIS" >/dev/null
for _ in $(seq 1 30); do [ "$(redis_cli PING 2>/dev/null)" = "PONG" ] && break; sleep 1; done
cached_scripts() { redis_cli INFO memory | tr -d '\r' | sed -n 's/^number_of_cached_scripts://p'; }
[ "$(cached_scripts)" = "0" ] || fail "Redis still has cached scripts after restart"
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $access" "$BASE/admin/api/v1/auth/me")"
[ "$code" = "200" ] || fail "first request after Redis restart returned $code"
[ "$(cached_scripts)" -ge 1 ] || fail "rate-limit script was not reloaded"
pass "first request after restart -> 200 (reconnected; rate-limit script reloaded)"

step "Rate limiting over HTTP (per client)"
codes="$(seq 1 40 | xargs -P 20 -I{} curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $access" -H 'X-Forwarded-For: 198.51.100.1' \
  "$BASE/admin/api/v1/auth/me" | sort | uniq -c | tr '\n' ' ')"
grep -q ' 429' <<<" $codes" || fail "no 429 in a burst of 40 requests from one client: $codes"
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $access" -H 'X-Forwarded-For: 198.51.100.2' "$BASE/admin/api/v1/auth/me")"
[ "$code" = "200" ] || fail "another client was limited too ($code)"
limiter_ttl="$(redis_cli PTTL 'newlife-core-api:rate_limiter:default:198.51.100.1:/admin/api/v1/auth/me')"
[ "$limiter_ttl" -gt 0 ] || fail "per-client limiter key has no TTL ($limiter_ttl)"
pass "one client's burst of 40 -> $codes; another client -> 200; limiter key expires in ${limiter_ttl}ms"

step "Graceful stop"
docker stop -t 30 "$API" >/dev/null
exit_code="$(docker inspect -f '{{.State.ExitCode}}' "$API")"
docker logs "$API" 2>&1 | grep -q "Lifespan finished" || fail "lifespan shutdown did not finish"
[ "$exit_code" = "0" ] || fail "container exit code $exit_code"
pass "SIGTERM -> lifespan finished, exit code 0"

printf '\nSMOKE PASSED  image=%s id=%s\n' "$IMAGE" "$IMAGE_ID"
