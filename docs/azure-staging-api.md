# Staging Core API on Azure

Runbook for [EFC-295](https://linear.app/jayhsia/issue/EFC-295) under the [Azure deployment plan](azure-deployment.md) and [ADR 0039](adr/0039-azure-deployment-and-release-direction.md). Builds on the [Core API image runbook](azure-core-api-image.md) and the [shared registry runbook](azure-container-registry.md).

Execution boundary: agents author Bicep, scripts, docs, and offline/local checks only. Every step below marked **(human)** is performed by a human operator. No agent or CI job signs in to Azure, runs `what-if` or deployments, sets secrets, changes DNS or firewall rules, migrates the Azure database, or deploys the app.

| Verification | Who | Status |
| --- | --- | --- |
| `scripts/validate-bicep.sh` (compile, lint, format; warnings fail) | Agent | Passed 2026-11-12, Bicep CLI 0.49.2 |
| `uv run pytest tests/infra/test_api_bicep.py` (policy checks on both compiled templates) | Agent | Passed 2026-11-12 |
| Account checks, `what-if`, deployment, secrets, migration, DNS/TLS, live checks | Human operator | **Pending** — see [Acceptance checklist](#acceptance-checklist-human) |

Offline validation does not prove that Azure accepts the template, that the SKUs exist in Canada East, or that the app works there. Only the operator's `what-if`, deployment, and live checks do.

Network: the ticket text asks for a VNet, Private Endpoints, Private DNS, and private-only Redis. The spec revision of 2026-11-10 ([EFC-292](https://linear.app/jayhsia/issue/EFC-292)) removed all of them for cost, and this template follows the revision: public endpoints, a PostgreSQL exact-IP allowlist, and Redis protected by access key and TLS.

## What the templates create

Two templates, both deployed into the staging resource group:

- `infra/azure/api/main.bicep` with `staging.bicepparam`: the App Service and data services. Redeployed whenever infrastructure or the image changes.
- `infra/azure/api-domain/main.bicep` with `staging.bicepparam`: the custom hostname, DNS records, and TLS certificate. Deployed **once**, after the Web App exists. API redeployments never touch it, so HTTPS on the hostname stays up. App Service renews the managed certificate by itself.

Names are proposals; the operator confirms they are free.

| Resource | Staging name | Settings |
| --- | --- | --- |
| App Service Plan | `asp-newlife-api-stg` | Linux, `B1`, 1 instance. Phase 2 only. |
| Web App for Containers | `app-newlife-api-stg` | Image `efcnewlifecr.azurecr.io/newlife-core-api@<digest>`, pulled with its system-assigned identity. Always On, `WEBSITES_PORT=8000`, HTTPS only, TLS 1.2, FTP and SCM basic auth off. Phase 2 only. |
| PostgreSQL Flexible Server | `psql-newlife-stg` | Version 18, Burstable `Standard_B1ms`, 32 GiB (no auto-grow), 14-day backups, no HA, no geo backup. Public access with exact-IP firewall rules only. `require_secure_transport=ON`. Database `newlife-core`. |
| Azure Managed Redis | `redis-newlife-stg` | `Balanced_B0`, **HA disabled**, TLS 1.2, port 10000, non-clustered policy, `NoEviction`, access keys on. Public network access (no IP allowlist exists). |
| Storage account | `stnewlifecorestg` | StorageV2, Standard LRS, Hot, no hierarchical namespace, no anonymous blob access, TLS 1.2. Blob and container soft delete 14 days. Private container `files`. |
| Key Vault | `kv-newlife-stg` | Standard, Azure RBAC, soft delete 90 days, purge protection on. Public endpoint (App Service resolves references over it). |
| DNS records | in the existing `efcnewlife.com` zone | `CNAME api.dev → app-newlife-api-stg.azurewebsites.net`, `TXT asuid.api.dev → <domain verification ID>`. The zone is referenced, never created. `api-domain` template. |
| Hostname and TLS | `api.dev.efcnewlife.com` | Hostname binding, free App Service managed certificate, SNI binding. `api-domain` template. |
| Role assignments | — | Web App identity: `Key Vault Secrets User` on the vault and `AcrPull` on the shared registry. Operators in `keyVaultSecretsOfficers`: `Key Vault Secrets Officer` on the vault. |

Not created: VNet, Private Endpoints, Private DNS zones, NAT Gateway, VPN, the shared registry (EFC-294), and the DNS zone.

The API template deploys in two phases, chosen by `NEWLIFE_API_IMAGE_DIGEST`:

- **Phase 1** (unset): Key Vault, PostgreSQL, Redis, Storage, and the secrets the template can write. No compute is billed yet. The operator then sets the remaining secrets and migrates the empty database.
- **Phase 2** (set to an image digest): adds the Plan, Web App, role assignments, and app outbound IP firewall rules. Every secret and the schema are in place before the app first starts. Its new role assignments take a few minutes to apply, so the first start usually needs one restart (step 6).

### App settings

All settings are owned by the template. A deployment replaces the whole set, so a setting added by hand in the portal is removed by the next deployment. Change settings in `main.bicep` instead.

| Setting | Staging value |
| --- | --- |
| `ENV` | `stg` |
| `VERSION` | `NEWLIFE_API_RELEASE` (short commit, ADR 0038) |
| `WEBSITES_PORT` / `WEB_CONCURRENCY` | `8000` / `1` |
| `APP_FQDN` | `api.dev.efcnewlife.com` |
| `ADMIN_PORTAL_URL` / `FACILITY_BOOKING_BASE_URL` | `https://portal.dev.efcnewlife.com` / `https://booking.dev.efcnewlife.com` |
| `CORS_ALLOWED_ORIGINS` | both origins above |
| `MEMBER_WEB_APPS` | `facility-booking\|https://booking.dev.efcnewlife.com` |
| `DATABASE_HOST` / `DATABASE_PORT` / `DATABASE_USER` / `DATABASE_NAME` | server FQDN / `5432` / `newlifeadmin` / `newlife-core` |
| `PGSSLMODE` / `PGSSLROOTCERT` | `verify-full` / `/etc/ssl/certs/ca-certificates.crt` |
| `STORAGE_BACKEND` / `AZURE_STORAGE_ACCOUNT_NAME` / `AZURE_STORAGE_CONTAINER_NAME` / `AZURE_STORAGE_REGION` | `azure_blob` / account name / `files` / `canadaeast` |
| `AZURE_TENANT_ID` / `AZURE_APP_CLIENT_ID` / `SENTRY_DSN` | from `staging.bicepparam` (not secrets) |
| `MOCK_LOGIN_ENABLED` | `true` (forced `false` whenever `ENV=prod`) |
| `GRAPH_MAIL_SEND_ENABLED` | `false` |
| Key Vault references | `DATABASE_PASSWORD`, `REDIS_URL`, `JWT_SECRET_KEY`, `REFRESH_TOKEN_HASH_SALT`, `REFRESH_TOKEN_HASH_PEPPER`, `DOCS_BASIC_AUTH_PASSWORD`, `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_APP_CLIENT_SECRET`, `MOCK_LOGIN_SECRET` |

The app uses the PostgreSQL administrator login. A separate least-privilege runtime role is not part of this ticket.

### Secrets

| Key Vault secret | App setting | Written by |
| --- | --- | --- |
| `database-password` | `DATABASE_PASSWORD` | Template, from `NEWLIFE_PG_ADMIN_PASSWORD` |
| `redis-url` | `REDIS_URL` | Template: `rediss://:<percent-encoded primary key>@<host>:10000/0` |
| `storage-connection-string` | `AZURE_STORAGE_CONNECTION_STRING` | Template, from the account key |
| `jwt-secret-key` | `JWT_SECRET_KEY` | Operator |
| `refresh-token-hash-salt` | `REFRESH_TOKEN_HASH_SALT` | Operator |
| `refresh-token-hash-pepper` | `REFRESH_TOKEN_HASH_PEPPER` | Operator |
| `docs-basic-auth-password` | `DOCS_BASIC_AUTH_PASSWORD` | Operator (otherwise the API docs password is the code default `developer`) |
| `azure-app-client-secret` | `AZURE_APP_CLIENT_SECRET` | Operator, from the Entra app registration |
| `mock-login-secret` | `MOCK_LOGIN_SECRET` | Operator |

A missing secret does not stop the app: App Service passes the literal `@Microsoft.KeyVault(...)` text as the value. For `JWT_SECRET_KEY` that would sign tokens with a known string. Set every operator secret before phase 2, and check that every reference resolves.

No secret appears in Git, template outputs, or the parameter file.

## Identities and permissions

| Who | Needs | Why |
| --- | --- | --- |
| Deploying operator | `Contributor` + `Role Based Access Control Administrator` (or `Owner`) on `rg-newlife-staging` | Create resources and their role assignments |
| Deploying operator | `Role Based Access Control Administrator` on the registry (or `rg-newlife-shared`) | Create the Web App's `AcrPull` assignment |
| Deploying operator | `DNS Zone Contributor` on the `efcnewlife.com` zone | Create `api.dev` and `asuid.api.dev` (`api-domain` template only) |
| Deploying operator | `Key Vault Secrets Officer` on the vault (granted by this template through `keyVaultSecretsOfficers`) | Set and read secrets with `az keyvault secret` |
| Staging Web App (system-assigned identity) | `AcrPull` on the registry, `Key Vault Secrets User` on the vault | Pull the image; resolve Key Vault references |
| GitHub Actions | **None** | CI has no Azure identity |

The registry template (`infra/azure/registry/`) does not need a separate `AcrPull` entry for this Web App. The API template creates it with the same assignment name, so adding it there too is harmless.

## Steps (human)

Run from a clean checkout of the commit you are deploying. Commands assume zsh or bash.

```bash
SUB="<grant subscription>"
RG=rg-newlife-staging
LOC=canadaeast
KV=kv-newlife-stg
APP=app-newlife-api-stg
PG=psql-newlife-stg
PARAMS=infra/azure/api/staging.bicepparam
TEMPLATE=infra/azure/api/main.bicep
```

### 1. Account and cost checks

```bash
az login
az account set --subscription "$SUB"
az account show --query '{name:name, id:id, tenant:tenantId}' -o table
```

- In Cost Management, confirm the grant's remaining credit and expiry, the spending-limit behaviour, and what else already uses the grant. Compare with `infra/azure/cost/estimate.csv` (staging rows).
- Check that Canada East offers what the template asks for:

  ```bash
  az postgres flexible-server list-skus --location "$LOC" -o json \
    | jq '[.[].supportedServerEditions[]? | select(.name=="Burstable") | .supportedServerSkus[]?.name] | index("Standard_B1ms") != null'
  az postgres flexible-server list-skus --location "$LOC" -o json \
    | jq '[.[].supportedServerVersions[]?.name] | unique'      # expect "18"
  az provider show --namespace Microsoft.Cache --query "resourceTypes[?resourceType=='redisEnterprise'].locations" -o tsv | tr '\t' '\n' | grep -i "canada east"
  az appservice list-locations --sku B1 --linux-workers-enabled -o tsv | grep -i "canada east"
  ```

  Managed Redis `Balanced_B0` availability and price: check in the Azure portal create blade or pricing calculator for Canada East. If any check fails, stop and record it on the ticket. Do not switch region or SKU without a decision.
- Confirm `efcnewlife.com` is an Azure DNS zone you can edit, and note its resource group. If a delegated child zone `dev.efcnewlife.com` exists, set `dnsZoneName = 'dev.efcnewlife.com'` and `dnsRecordName = 'api'` in `infra/azure/api-domain/staging.bicepparam` instead.
- Check CAA records. If any exist, they must allow the App Service managed certificate issuer: `az network dns record-set caa list -g <zone RG> -z efcnewlife.com -o table`.
- Confirm the shared registry exists and an image record (EFC-294) is available for the commit you deploy.
- Check that the proposed names are free. `NXDOMAIN` means free; an answer means taken:

  ```bash
  for h in app-newlife-api-stg.azurewebsites.net psql-newlife-stg.postgres.database.azure.com kv-newlife-stg.vault.azure.net; do
    nslookup "$h" >/dev/null 2>&1 && echo "TAKEN $h" || echo "free  $h"; done
  az storage account check-name --name stnewlifecorestg --query nameAvailable
  az keyvault list-deleted --query "[?name=='$KV'].name" -o tsv     # must be empty (purge protection blocks reuse)
  ```

  If a name is taken, change it in `staging.bicepparam` and in the variables above.

### 2. Fill in the parameters

Edit `infra/azure/api/staging.bicepparam` and commit it (no secrets):

- `postgresOperatorIps`: your current public IPv4 (`curl -s https://api.ipify.org`), as `{ name: '<you>-<place>', ip: '<ip>' }`. Exact addresses only; never `0.0.0.0`.
- `keyVaultSecretsOfficers`: `{ principalId: '<az ad signed-in-user show --query id -o tsv>', principalType: 'User' }`.
- `azureTenantId`, `azureAppClientId`: the Entra tenant and the Admin Portal SPA app registration (the same client ID the portal uses as `VITE_AZURE_CLIENT_ID`).
- `sentryDsn`: the Core API staging DSN, or leave empty to disable telemetry.

Edit `infra/azure/api-domain/staging.bicepparam` and commit it:

- `dnsZoneResourceGroup`: the zone's resource group.

```bash
scripts/validate-bicep.sh
```

### 3. Phase 1: data services and Key Vault

```bash
az group create --name "$RG" --location "$LOC" --tags app=newlife owner=newlife-core-api environment=staging

# New password: letters, digits, and '-' only (it is placed in a database URL unencoded).
export NEWLIFE_PG_ADMIN_PASSWORD="$(openssl rand -hex 20)Aa-"
unset NEWLIFE_API_IMAGE_DIGEST NEWLIFE_API_RELEASE

az deployment group what-if --resource-group "$RG" --template-file "$TEMPLATE" --parameters "$PARAMS"
```

Expect only creates: one Key Vault, three secrets (`database-password`, `redis-url`, `storage-connection-string`), your `Key Vault Secrets Officer` assignment, one PostgreSQL server with one configuration, one database and your operator firewall rule(s), one Redis cluster with database `default` (HA `Disabled`), one storage account with blob service and container `files`. No Plan, Web App, DNS records, or certificate. No `Microsoft.Network/privateEndpoints` or `virtualNetworks`.

```bash
az deployment group create --resource-group "$RG" --name newlife-api-staging \
  --template-file "$TEMPLATE" --parameters "$PARAMS"
az deployment group show --resource-group "$RG" --name newlife-api-staging --query properties.outputs -o json
```

PostgreSQL and Redis can take 10–20 minutes. From now on, PostgreSQL, Redis, and Storage are billed.

Every later deployment needs the same password. Read it back from the vault instead of generating a new one:

```bash
export NEWLIFE_PG_ADMIN_PASSWORD="$(az keyvault secret show --vault-name "$KV" --name database-password --query value -o tsv)"
```

### 4. Operator secrets

Role assignments can take a few minutes to apply. If `Forbidden`, wait and retry.

```bash
for name in jwt-secret-key refresh-token-hash-salt refresh-token-hash-pepper docs-basic-auth-password mock-login-secret; do
  az keyvault secret set --vault-name "$KV" --name "$name" --value "$(openssl rand -hex 32)" --query name -o tsv
done

# Entra client secret from the app registration (Certificates & secrets). Typed, not echoed.
read -rs AZURE_APP_CLIENT_SECRET
az keyvault secret set --vault-name "$KV" --name azure-app-client-secret --value "$AZURE_APP_CLIENT_SECRET" --query name -o tsv
unset AZURE_APP_CLIENT_SECRET

# All nine must be listed.
az keyvault secret list --vault-name "$KV" --query "[].name" -o tsv | sort
```

Share `docs-basic-auth-password` and `mock-login-secret` with testers out of band (`az keyvault secret show`), never on the ticket.

### 5. Initial migration and Catalog bootstrap

From your allowlisted machine, in a clean worktree of the exact commit of the image you will deploy (no `.env` there, so local settings cannot leak in):

```bash
REV=<full commit SHA of the image record>
git worktree add ../newlife-core-api-stg "$REV"
cd ../newlife-core-api-stg && uv sync --frozen

export ENV=stg
export DATABASE_HOST="$PG.postgres.database.azure.com" DATABASE_PORT=5432 DATABASE_USER=newlifeadmin DATABASE_NAME=newlife-core
export DATABASE_PASSWORD="$(az keyvault secret show --vault-name "$KV" --name database-password --query value -o tsv)"
export PGSSLMODE=verify-full PGSSLROOTCERT="$(uv run python -c 'import certifi; print(certifi.where())')"

# TLS and version. Firewall changes can take a minute: up to 5 tries, 30 s apart, then stop and investigate.
for i in 1 2 3 4 5; do
  PGPASSWORD="$DATABASE_PASSWORD" psql "host=$DATABASE_HOST port=5432 dbname=$DATABASE_NAME user=$DATABASE_USER sslmode=verify-full sslrootcert=$PGSSLROOTCERT connect_timeout=10" \
    -c 'select version();' && break
  [ "$i" = 5 ] && echo "PostgreSQL unreachable after 5 tries" && break
  sleep 30
done
# Expect PostgreSQL 18.x. With sslmode=disable the server must refuse the connection.

uv run alembic current      # expect no revision on a new database
uv run alembic upgrade head
uv run alembic current      # expect the head revision of $REV; record it
uv run python -m portal.cli.main init-all   # catalog seed, then an interactive superuser prompt
```

Never run `alembic downgrade` or delete data here. If `upgrade head` fails, stop: do not run phase 2, and post the revision shown by `alembic current` and the error message without connection details. Afterwards remove the worktree (`git worktree remove ../newlife-core-api-stg`) and unset the exported variables.

### 6. Phase 2: App Service

Use the image record from the [registry runbook](azure-container-registry.md#publish-verify-and-lock-human):

```bash
export NEWLIFE_API_IMAGE_DIGEST=sha256:<digest from the image record>
export NEWLIFE_API_RELEASE=<first 7 characters of the commit>
export NEWLIFE_PG_ADMIN_PASSWORD="$(az keyvault secret show --vault-name "$KV" --name database-password --query value -o tsv)"

az deployment group what-if --resource-group "$RG" --template-file "$TEMPLATE" --parameters "$PARAMS"
```

Expect the phase 1 resources unchanged (`NoChange`, or `Ignore` for read-only properties) and creates for the Plan (`B1`), Web App, its `logs` config, two publishing-credential policies, the `Key Vault Secrets User` assignment, the `AcrPull` assignment in `rg-newlife-shared`, and `app-outbound-*` firewall rules. No DNS records, hostname binding, or certificate. Check that `linuxFxVersion` shows the digest you expect.

```bash
az deployment group create --resource-group "$RG" --name newlife-api-staging \
  --template-file "$TEMPLATE" --parameters "$PARAMS"
az deployment group show --resource-group "$RG" --name newlife-api-staging --query properties.outputs -o json
```

The Web App starts before its new role assignments take effect, so the first image pull or Key Vault resolution can fail. Wait about five minutes, then restart:

```bash
az webapp restart --resource-group "$RG" --name "$APP"
```

### 7. Custom domain and TLS (once)

Run only after phase 2 succeeded. Later API deployments do not need this step.

```bash
DOMAIN_TEMPLATE=infra/azure/api-domain/main.bicep
DOMAIN_PARAMS=infra/azure/api-domain/staging.bicepparam

az deployment group what-if --resource-group "$RG" --template-file "$DOMAIN_TEMPLATE" --parameters "$DOMAIN_PARAMS"
```

Expect only creates: `CNAME api.dev` and `TXT asuid.api.dev` in the zone's resource group, the hostname binding on `app-newlife-api-stg`, and one managed certificate. Nothing else in the zone changes.

```bash
az deployment group create --resource-group "$RG" --name newlife-api-domain-staging \
  --template-file "$DOMAIN_TEMPLATE" --parameters "$DOMAIN_PARAMS"
az deployment group show --resource-group "$RG" --name newlife-api-domain-staging --query properties.outputs -o json
```

The managed certificate can take several minutes. If it fails because the hostname cannot be validated, check `dig +short CNAME api.dev.efcnewlife.com` and `dig +short TXT asuid.api.dev.efcnewlife.com`, wait a few minutes, and run the same `create` again.

Rerun this template only to change the hostname. A rerun binds TLS again, so HTTPS on the hostname drops briefly while it runs.

### 8. Entra and API origins

- API origins are already set by the template: `CORS_ALLOWED_ORIGINS` and `MEMBER_WEB_APPS` allow exactly `https://portal.dev.efcnewlife.com` and `https://booking.dev.efcnewlife.com`. Change them only in `staging.bicepparam`.
- `azureTenantId` and `azureAppClientId` (step 2) must be filled in, or Microsoft sign-in fails. Check: `az webapp config appsettings list -g "$RG" -n "$APP" --query "[?name=='AZURE_APP_CLIENT_ID'].value" -o tsv` is not empty.
- On that app registration, the API needs no redirect URI of its own. The frontends' redirect URIs (`https://portal.dev.efcnewlife.com`, `https://booking.dev.efcnewlife.com`) belong to [EFC-297](https://linear.app/jayhsia/issue/EFC-297) and [EFC-298](https://linear.app/jayhsia/issue/EFC-298). Until they exist, test Admin sign-in with password login or Microsoft token exchange from a client you control.

## Diagnostics inside App Service (human)

The image has no SSH server, so there is no shell in the app container. Evidence from inside App Service comes from the app itself:

```bash
# Key Vault references: every entry must show "Resolved".
APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)
az rest --method get --url "https://management.azure.com$APP_ID/config/configreferences/appsettings?api-version=2024-11-01" \
  --query "value[].{name:name, status:properties.status}" -o table

# Container log stream: startup proves database and Redis TLS from the app's own network.
az webapp log tail --resource-group "$RG" --name "$APP"
```

Expect in the log stream: `Listening at: http://0.0.0.0:8000`, `Redis rate limiters initialized`, `Pending-payment expiry sweep started`, and no `Failed to initialize Redis rate limiters`, `SSL`, `ClientConfigurationError`, or image pull errors. Use the portal's **Diagnose and solve problems** for container start failures.

## Live verification (human)

```bash
curl -i https://api.dev.efcnewlife.com/healthz          # 200, no certificate error
curl -sv https://api.dev.efcnewlife.com/healthz 2>&1 | grep -E 'subject:|issuer:|expire date:'
curl -i http://api.dev.efcnewlife.com/healthz           # 301 to https

# PostgreSQL: only exact-IP rules (start == end), no 0.0.0.0 rule.
az postgres flexible-server firewall-rule list -g "$RG" -n "$PG" -o table
az postgres flexible-server parameter show -g "$RG" -s "$PG" -n require_secure_transport --query value -o tsv   # ON

# Redis: HA disabled, TLS only, access keys on, non-clustered.
az redisenterprise show -g "$RG" -n redis-newlife-stg --query '{sku:sku.name, ha:highAvailability, tls:minimumTlsVersion, public:publicNetworkAccess}' -o table
az redisenterprise database show -g "$RG" --cluster-name redis-newlife-stg --query '{protocol:clientProtocol, policy:clusteringPolicy, eviction:evictionPolicy, keys:accessKeysAuthentication}' -o table

# Blob: anonymous access must fail.
curl -s -o /dev/null -w '%{http_code}\n' "https://stnewlifecorestg.blob.core.windows.net/files?restype=container&comp=list"   # 404 or 409, never 200
```

Then, with a controlled test account and no real member notifications:

1. **Sign-in:** Admin login, `GET /admin/api/v1/auth/me`, refresh, logout; the old refresh token is rejected (`401`). This exercises PostgreSQL and Redis.
2. **Files:** upload an attachment through the Admin Portal or API, open its signed link in a browser (works), then open the same URL without the query string (fails).
3. **Expiry sweep:** leave the app idle for 30+ minutes. The log stream still shows sweep activity, and there is no cold start on the next request (Always On).
4. **Image checks:** run [Operator tests on Azure](azure-core-api-image.md#operator-tests-on-azure-human) 1–7 for staging.
5. **Outbound IPs:** compare `az webapp show -g "$RG" -n "$APP" --query possibleOutboundIpAddresses -o tsv` with the `app-outbound-*` rules. They must match. Repeat after any Plan scale change, and redeploy to add new ones.

## Later deployments (human)

- **Always set `NEWLIFE_API_IMAGE_DIGEST` to the digest staging should run.** An infrastructure deployment with an older digest rolls the app back. To keep the running image:
  `az webapp config show -g "$RG" -n "$APP" --query linuxFxVersion -o tsv` (the part after `@`).
- API deployments leave the custom domain and certificate alone; do not rerun the `api-domain` template for them. App settings changes restart the app. Basic has no slots.
- Deployments are incremental. Removing an IP from `postgresOperatorIps` or a principal from `keyVaultSecretsOfficers` does not delete the rule or assignment. Remove it by hand:
  `az postgres flexible-server firewall-rule delete -g "$RG" -n "$PG" --rule-name operator-<name> --yes`
- Temporary single-IP rules for migrations and their cleanup belong to the release procedure ([EFC-296](https://linear.app/jayhsia/issue/EFC-296)).

## If something fails

- Read the deployment error (`az deployment operation group list -g "$RG" -n newlife-api-staging --query "[?properties.provisioningState=='Failed']"`) and the App Service log stream first.
- Do not open PostgreSQL to all IPs or Azure services, and do not turn on anything broader on Redis, to work around a DNS, TLS, or firewall problem.
- A failed migration stops the rollout. Report the revision and a sanitised error; do not downgrade.
- Stopping the Web App does not stop the Plan's charge. Deleting a failed resource is a human decision; the Key Vault name stays reserved for 90 days after deletion because of purge protection.

## Acceptance checklist (human)

All items stay pending until the operator posts evidence on EFC-295 (no keys, passwords, tokens, or personal data).

- [ ] Account, grant, Canada East SKU (PostgreSQL 18 `Standard_B1ms`, Redis `Balanced_B0`, Linux `B1`), DNS zone, and CAA checks recorded.
- [ ] Phase 1 `what-if` matched the expected list; deployment succeeded.
- [ ] All nine secrets exist; no secret value posted anywhere.
- [ ] Initial migration reached head; `alembic current` revision recorded; `init-all` finished.
- [ ] Phase 2 `what-if` matched; deployment succeeded; every Key Vault reference `Resolved`.
- [ ] Domain `what-if` matched; deployment succeeded; certificate issued.
- [ ] Log stream shows port 8000, Redis rate limiters, and the expiry sweep, with no pull, TLS, or connection errors.
- [ ] `https://api.dev.efcnewlife.com/healthz` returns `200` with a valid certificate.
- [ ] PostgreSQL rules are exact IPs only (operators plus every possible outbound IP); `require_secure_transport` is `ON`.
- [ ] Redis HA disabled, TLS, non-clustered policy, access keys on.
- [ ] Sign-in, refresh, logout, revoked refresh token checks passed.
- [ ] Authorised file link works; anonymous access fails.
- [ ] Expiry sweep still running after 30+ minutes idle.
- [ ] After one more API deployment (same digest), `api.dev` is still bound with the same certificate and HTTPS never failed.
- [ ] Outputs table filled in.

Evidence template:

```text
Operator: <name>   Date/time (UTC): <…>   Environment: staging   Subscription: <name>
Commit: <full SHA>   Image: efcnewlifecr.azurecr.io/newlife-core-api@sha256:<…>   VERSION: <short SHA>
Phase 1: pass/fail <notes>   Phase 2: pass/fail <notes>   Domain: pass/fail <notes>   Alembic revision: <rev>
Key Vault references resolved: yes/no   Log stream: pass/fail   healthz/TLS: pass/fail
PG rules exact-IP: yes/no   Redis HA/TLS/policy: pass/fail   Auth: pass/fail   Files: pass/fail   Expiry: pass/fail
Cleanup / follow-ups: <…>
```

### Outputs

| Output | Expected | Actual (operator) |
| --- | --- | --- |
| `keyVaultName` / `keyVaultUri` | `kv-newlife-stg` / `https://kv-newlife-stg.vault.azure.net/` | |
| `postgresFqdn` | `psql-newlife-stg.postgres.database.azure.com` | |
| `redisHostName` | `redis-newlife-stg.canadaeast.redis.azure.net` | |
| `storageAccountName` | `stnewlifecorestg` | |
| `webAppName` / `webAppDefaultHostName` | `app-newlife-api-stg` / `app-newlife-api-stg.azurewebsites.net` | |
| `webAppPrincipalId` | a GUID | |
| `webAppPossibleOutboundIps` | comma-separated IPv4 list, same as the `app-outbound-*` rules | |
| `hostName` (domain template) | `api.dev.efcnewlife.com` | |
| `certificateThumbprint` (domain template) | 40 hex characters | |
