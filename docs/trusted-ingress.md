# Trusted ingress and client IP

Application contract for [EFC-336](https://linear.app/jayhsia/issue/EFC-336) under the [EFC-328 spec](https://linear.app/jayhsia/issue/EFC-328). [EFC-337](https://linear.app/jayhsia/issue/EFC-337) in `newlife-infra` consumes it for App Service access restrictions, the Cloudflare Transform Rule, Key Vault, and live acceptance.

Execution boundary: agents author code, tests, and the local image smoke only. Every Azure, Cloudflare, Key Vault, and secret operation is performed by a human operator. **Offline completion is not Cloudflare or Azure acceptance.**

## What the application does

`TrustedIngressMiddleware` (`portal/middlewares/trusted_ingress.py`) is the outermost middleware of the public application. It runs before CORS (including preflight `OPTIONS`), the rate limit, the request context, both mounted apps (`/admin`, `/api`), audit, and refresh-token writes.

It resolves one canonical client IP per request (`portal/libs/client_ip.py`). That value is the rate-limit identifier (`<ip>:<path>`), `RequestContext.ip`, the audit `ip_address`, and refresh-token / device `last_ip`. No consumer reads `X-Forwarded-For`, `X-Real-IP`, or `CF-Connecting-IP` itself. IPv4-mapped IPv6 (`::ffff:a.b.c.d`) becomes IPv4; IPv6 uses its compressed lowercase form.

| Mode                   | Client IP                         | Rejected with `403 {"detail": "Forbidden"}`                                                                                                                                          |
| ---------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `direct` (default)     | Transport peer (`scope["client"]`) | Nothing. All forwarding headers are ignored.                                                                                                                                         |
| `cloudflare`           | The single `CF-Connecting-IP`      | Missing, empty, duplicate, or wrong `X-NewLife-Origin-Secret`; `Host` other than `APP_FQDN` (or duplicated); missing, duplicate, list-valued, zoned, or malformed `CF-Connecting-IP`. |

- The secret check uses `hmac.compare_digest`. The check order is secret, host, client IP; the log line names only the failed category (`Rejected request from untrusted ingress: invalid origin secret|host|client IP`), never a header value.
- `X-NewLife-Origin-Secret` is removed from the request headers in both modes, so the application, request context, Sentry trace continuation, and logs never see it. Rejection bodies are constant.
- There is no fallback to `X-Forwarded-For` / `X-Real-IP`, and no identity is invented: a request without a trustworthy address has no `ip`, and its limiter key uses `unknown`.

### Probe exceptions

Only `GET` and `HEAD` on exactly `/healthz` of the public application bypass the cloudflare-mode checks. They get no client IP. `/healthz` returns `{"message": "ok"}` only. `HEAD` reaches the GET-only route and gets `405`, not `403`. Everything else is checked, including `/healthz/`, `POST /healthz`, `/`, `/docs`, `/openapi.json`, `/admin/*`, `/api/*`, and CORS preflight. No `User-Agent` or other header grants an exception.

No warm-up exception is added. App Service health check calls `GET /healthz`. Always On and container start-up pings are expected to need only an HTTP response from the container; a `403` on `/` is one, produced before any business code runs. This is unverified: live acceptance confirms it. If it fails, add a narrow path/method exception, never a header exception.

## Configuration

| Setting                    | Value                                                     | Notes                                                                                                                                 |
| -------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `TRUSTED_PROXY_MODE`       | `direct` (default) or `cloudflare`                         | Any other value fails startup.                                                                                                        |
| `CLOUDFLARE_ORIGIN_SECRET` | Key Vault reference; at least 32 characters                | Required in cloudflare mode, ignored in direct mode. Generate high-entropy (e.g. `openssl rand -hex 32`) in a human-operated procedure. |
| `APP_FQDN`                 | `api-dev.efcnewlife.com` (staging)                         | Already set by the `app-service` template. Cloudflare mode accepts only this `Host` (case-insensitive, no port).                       |

Surrounding whitespace in the secret is stripped before use. Invalid cloudflare-mode settings raise `TrustedProxyConfigError` while the application is built, so gunicorn workers fail to boot. That includes a value starting with `@Microsoft.KeyVault(` (any case): App Service passes an unresolved reference through as its own text, which is public in `newlife-infra`. The error names the setting, never its value. `CLOUDFLARE_ORIGIN_SECRET` is a `SecretStr`, so it never shows in the configuration's `repr`. The value must not be in Git, parameter files, `zone.json`, frontend builds, logs, Sentry, or response headers. Browsers never send it.

## Server forwarding settings

- **Image (gunicorn ASGI worker, `entrypoint.sh`):** `scope["client"]` is always the socket peer. `FORWARDED_ALLOW_IPS` affects only the scheme (`X-Forwarded-Proto` and similar), never the client address. PROXY protocol stays `off` (default). Do not change either for client attribution.
- **Local uvicorn:** run with `--no-proxy-headers` (`python -m portal` passes `proxy_headers=False`). Otherwise uvicorn rewrites the peer from `X-Forwarded-For` for requests from `127.0.0.1`.

In direct mode behind App Service, the transport peer is expected to be an App Service front-end address, not the visitor (to confirm live). All visitors would then share one rate-limit bucket per path, and audit / `last_ip` would record that front-end address. That is the intended fail-safe until cloudflare mode is active; it is not visitor attribution.

## Required ingress protections (EFC-337)

The origin secret alone does not prove the visitor IP is unmodified, and Cloudflare CIDRs alone do not authenticate this zone. Cloudflare mode is only trustworthy with all of these:

1. App Service main-site access restrictions: allow Cloudflare IPv4/IPv6 CIDRs, deny unmatched. SCM keeps its own rules.
2. A zone request-header Transform Rule that **sets** (overwrites, never appends) `X-NewLife-Origin-Secret` on `api-dev.efcnewlife.com` only.
3. Cloudflare proxy on, SSL Full (strict); no Worker proxies API requests, and Worker subrequests to the API are blocked at the edge.
4. Pseudo IPv4 is **Off** (or "Add header"), never "Overwrite headers": overwrite puts a hashed Class E address (`240.0.0.0/4`) into `CF-Connecting-IP`, which the API accepts as the client. The "Remove visitor IP headers" managed transform stays off; without `CF-Connecting-IP` every protected request gets `403`.

## Activation sequence (human, staging)

1. Deploy an image containing this change. It stays in direct mode.
2. Generate the secret; store it in staging Key Vault and in the Transform Rule. Enable the rule.
3. Apply access restrictions (EFC-337 Bicep).
4. Set `TRUSTED_PROXY_MODE=cloudflare` and the `CLOUDFLARE_ORIGIN_SECRET` Key Vault reference through the `app-service` template; restart.
5. Run the pending live tests below.

Rollback: set `TRUSTED_PROXY_MODE=direct` (no secret needed) and restart. DNS-only recovery must switch to direct mode first: never keep cloudflare mode while the origin is reachable without the edge.

## Verification

| Check                                                                                                                                                                                                 | Who            | Status      |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | ----------- |
| `tests/test_trusted_ingress.py`: both modes, both mounted apps, CORS preflight, IPv4/IPv6, rejected headers, probe exceptions, redaction, startup rejection, rate limit / request / audit / `last_ip` agreement | Agent          | Passed 2026-11-20 |
| `scripts/local-image-smoke.sh`: real gunicorn image, direct mode ignores forged forwarding headers, cloudflare mode rejects untrusted ingress and limits per `CF-Connecting-IP`, secret absent from logs | Agent          | Passed 2026-11-20 |
| Pending live tests (EFC-337): `api-dev` `/healthz` 200 through Cloudflare, direct `azurewebsites.net` 403, health check and Always On healthy, Portal/Booking sign-in and CORS, per-client 429, forged-header and alternate-zone/Worker attempts rejected, CI deploy keeps protection | Human operator | **Pending** |
