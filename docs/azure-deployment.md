# Azure deployment plan

Design assembled on 2026-11-10 from the deployment interview. Decisions are recorded in [ADR 0039](adr/0039-azure-deployment-and-release-direction.md). This document proposes implementation details for final review; it does not report provisioned Azure resources or implemented pipelines.

## Mandatory execution boundary

Agents may author and review Bicep, source code, CSV estimates, workflow definitions, operator scripts, documentation, and offline tests only. Every Azure account or resource operation must be performed by a human operator. Agents must not sign in to Azure, inspect the live account, run Azure what-if/apply, create/update/delete resources, change DNS/RBAC/secrets/firewalls, push/pull images through ACR, deploy apps, run migrations against Azure databases, restore data, or trigger Azure-affecting workflows. Main/tag CI may validate/build and retain artifacts outside Azure, but must not automatically perform Azure operations. Do not give unattended CI Azure credentials. Public documentation/pricing research and local tests without live Azure access are allowed. Human execution and live verification must be explicitly attributed and must not be claimed complete without operator-supplied evidence.

This user instruction supersedes the earlier automatic Azure staging deployment/migration direction. Main and tag events prepare CI results and artifacts only; a human executes every Azure setup, publication, migration, deployment, inspection, drill, and cleanup. Agent acceptance is offline artifact validation; live acceptance remains pending human evidence.

## Scope and constraints

- Host Core API, Newlife Portal, and Facility Booking for approximately 200 users with low expected concurrency.
- Use Canada Central (Toronto) for regional resources. On 2026-11-12 the operator found PostgreSQL provisioning restricted in Canada East for the grant subscription, so the earlier Canada East choice is superseded (see [ADR 0039](adr/0039-azure-deployment-and-release-direction.md)). Validate each SKU, quota, and capacity before provisioning; Canada Central support for PostgreSQL 18 `Standard_B1ms`, Managed Redis `Balanced_B0`, and Linux App Service `B1` is a pending human check. Canada Central has Availability Zones, but this plan does not change the HA choices; whether production Redis HA spreads its nodes across zones is not part of the plan or the estimate.
- Use the USD 2,000 annual nonprofit grant, with no self-funded overage. Verify the actual grant period, remaining credit, eligible services, subscription spending-limit behavior, and other workloads before committing resources.
- Keep staging available around the clock. The user is the primary contact; email alerts are sufficient and overnight incidents can wait until the next day.
- Use independent repository versions and the existing `efcnewlife.com` Azure DNS zone. Its existence is user-reported, not independently verified.

## Resource layout

| Resource | Staging | Production |
| --- | --- | --- |
| Core API | Linux App Service Web App on its own Plan | Separate Linux App Service Web App and Plan |
| App Service sizing | B1 initial validation candidate, Always On | B1 initial validation candidate, Always On; independently adjustable |
| Portal | Its own Static Web App, Free | Its own Static Web App, Standard from launch |
| Facility Booking | Its own Static Web App, Free | Its own Static Web App, Standard from launch |
| PostgreSQL | Separate Flexible Server, B1ms candidate, 32 GiB estimating assumption | Separate server with the same initial estimating assumptions, subject to load testing |
| Managed Redis | Separate Balanced instance, smallest viable SKU, no HA | Separate Balanced instance, smallest viable SKU, HA enabled |
| Blob Storage | Separate Standard GPv2 account | Separate Standard GPv2 account |
| Key Vault | Separate vault | Separate vault |
| Network | Public endpoints; PostgreSQL firewall allowlist | Public endpoints; PostgreSQL firewall allowlist |
| Private Endpoints | None (removed for cost on 2026-11-10) | None |
| ACR | One shared Basic registry, explicit immutable image digest selection | Same registry |

Balanced B0 is the pricing candidate, not a reservation of capacity or a proven memory requirement. Validate client connection policy, TLS, connection limits, memory headroom, and behavior on restart/failover. Managed Redis supports database 0 only; Core API now keeps all Redis state in one database 0 keyspace (see the [Core API image and Managed Redis runbook](azure-core-api-image.md)). Prefer a compatible non-clustered policy initially if supported by the selected SKU, and test rate limiter operations rather than assuming compatibility.

Static Web Apps distributes static assets globally. It has no Canada region, so its supported resource region is selected separately; this is not a guarantee that frontend content stays in Canada. The API remains separately hosted on App Service, using the existing MSAL and API authentication flows.

## Repository ownership

The following directories are proposed. The shared ACR template is in `infra/azure/container-registry/` (see the [registry runbook](azure-container-registry.md)). Each environment's API uses one template per resource (see the [staging API runbook](azure-staging-api.md)): `infra/azure/key-vault/`, `postgres/`, `redis/`, `storage/`, `app-service/`, and the one-time `custom-domain/`. Other Bicep files and workflows are separate work.

| Repository | Proposed infrastructure directory | Owns |
| --- | --- | --- |
| `newlife-core-api` | `infra/azure/` | API apps/plans, PostgreSQL and its firewall allowlist, Redis, Blob, Key Vault, shared ACR, backend monitoring, `api` and `api.dev` DNS records |
| `newlife-portal-frontend` | `infra/azure/` | Two Portal Static Web Apps, domain bindings, `portal` and `portal.dev` DNS records, frontend workflows |
| `facility-booking-frontend` | `infra/azure/` | Two Booking Static Web Apps, domain bindings, `booking` and `booking.dev` DNS records, frontend workflows |

Keep Bicep modules reusable, with environment-specific parameters. Reference the existing public DNS zone; do not recreate or transfer it. Data services and credentials remain separate per environment.

Infrastructure delivery: the agent authors and offline-validates Bicep and operator procedures. The human runs Azure `what-if`, reviews changes/costs, and applies them. Routine CI has no Azure credentials and does not apply infrastructure or publish applications. Humans establish scoped operator/runtime identities and DNS/RBAC access, documenting actual permission boundaries. Agent-run cloud inspection is prohibited.

## Domains and connections

| Application | Production | Staging |
| --- | --- | --- |
| Core API | `api.efcnewlife.com` | `api.dev.efcnewlife.com` |
| Portal | `portal.efcnewlife.com` | `portal.dev.efcnewlife.com` |
| Booking | `booking.efcnewlife.com` | `booking.dev.efcnewlife.com` |

Here `dev` means staging, not local development. Configure exact HTTPS origins consistently in frontend builds, API CORS/member-app settings, Entra redirect URIs, and email/application links. Bind managed certificates to the full hostnames and verify the existing DNS/CAA configuration.

- API ingress is public HTTPS. The user removed Private Endpoints, Private DNS zones, and VNet integration on 2026-11-10 to save about USD 31/month; see the [cost estimate](../infra/azure/cost/README.md).
- PostgreSQL uses `Public access (allowed IP addresses)`. The firewall allows every App Service possible outbound IP plus explicit developer/operator IPs, with TLS required. Those outbound IPs are shared with other customers on the same deployment unit and can change, so re-check the list after scaling. Do not enable the all-Azure-services rule or unrestricted public access.
- Managed Redis has no IP allowlist, so both instances use public access from all networks, protected by access keys or Entra authentication and TLS. Sharing one instance between staging and production is under consideration, not selected.
- Blob endpoints remain reachable by external browsers for authorized/SAS URLs, with anonymous access disabled. Use Hot/LRS without hierarchical namespace, 14-day soft delete, and a 10 GB first-year live-data estimating assumption. There is no initial video workload.
- ACR Basic and Key Vault can use authenticated public endpoints initially. Use image-pull identity/RBAC and Key Vault references where supported; application secrets stay out of Git and frontend builds. The existing Blob adapter still uses connection-string/account-key SAS, so do not assume application-level managed identity conversion is already implemented.
- No Private Endpoint, NAT Gateway, permanent administration VM, VPN Gateway, or Container Apps environment is included.

## CI and deployment events

| Event | CI | Staging | Production |
| --- | --- | --- | --- |
| Pull request | Repository checks, tests, build validation | No privileged deployment by default | None |
| Update `main` | Required checks and non-Azure artifact preparation | Human deployment only | None |
| Update `release/x.y.z` | Required checks only | None from the branch event | None |
| Create eligible `x.y.z` tag | Verify release commit/CI and prepare artifacts outside Azure | Human deployment only | None |
| Human production release selecting tag | Review CI/artifacts and manually verify schema | No dependency on currently running staging | Human executes deployment |

All Azure-affecting publication steps are instructions/scripts for the human, never event-triggered execution or an agent-triggered workflow. CI may build/test and retain artifacts outside Azure. Tags have no `v` prefix, for example `0.3.0`. Protect release tags against movement/deletion. Each repository versions independently. A human may deploy a later `main` candidate over staging after a tagged version; production always uses the selected tag's immutable commit/artifact mapping.

Serialize backend deployment/migration operations per environment. Do not cancel a running migration just to deploy a newer commit. Queue later deployments and retain the exact run/commit identity. Determine compatibility before applying or deploying an older tagged version against a newer staging schema; block unknown or incompatible cases without downgrade or data reset.

### Core API artifacts

The agent builds/tests the container locally or in non-Azure CI before any human schema change. The human publishes it to ACR with a commit-to-digest record and retain digests needed for rollback. The human production release selects the tagged digest rather than rebuilding an unrecorded image or taking the currently deployed staging digest. Runtime settings and Sentry environment/release values can differ per environment.

Validate the container entrypoint, listening port, and App Service container configuration. Set Always On; Basic has no deployment slots, so allow for a restart/interruption and do not promise slot-swap or zero-downtime deployment. Preserve the existing Pending-payment expiry interval loop and locking behavior.

### Frontend artifacts

Use pnpm with the committed lockfile, package-read authentication for `@efcnewlife/newlife-ui`, type checks, relevant tests, and production/staging builds. API URLs and MSAL/Sentry settings are build-time inputs: build distinct environment artifacts from the same tagged source when needed. Do not promote staging `dist` unchanged to production when it embeds staging endpoints.

The human release procedure creates and uploads required source maps using the exact Sentry release ID used by that build. Source-map upload failure blocks publishing the new build while the running website remains available. Preserve [ADR 0038](adr/0038-sentry-observability-boundaries.md): `<repo>@<short-commit>` for staging and `<repo>@<version>` for production. Keep Sentry auth tokens and package tokens in CI secrets, never `VITE_*`.

Configure SPA navigation fallback and explicit cache behavior so direct links work and an old HTML entry point does not strand users on unavailable assets. Keep previous deployable artifacts for rollback. Smoke-test HTTPS, a deep link, login, and API connectivity after deployment.

## Migrations

Migration files remain human-managed; agents must not add, modify, or delete files under `alembic/versions/`.

### Staging: human-executed

1. The agent prepares the exact target checkout/image, migration entrypoint, local/mock checks, and an operator runbook. CI retains artifacts outside Azure only.
2. The human reviews the intended version, cost/account prerequisites, current revisions, and compatibility. The human adds their exact public IP to PostgreSQL if necessary and verifies TLS connectivity; firewall propagation may require bounded retries.
3. The human runs that target version's committed migrations, checks the exit status and resulting revisions, and removes any temporary rule they created. The human audits residual temporary rules without deleting unrelated developer rules.
4. The human publishes/selects the ACR digest and deploys the staging API, then performs real smoke checks and records evidence. No automatic staging migration or Azure deployment is enabled.

### Production: human-executed

The human selects/checks out the production tag, verifies recovery and backward compatibility, reads current revisions, and manually applies migrations over TLS from an allowlisted local IP. The human records the tag/revisions/result, publishes/selects the immutable image digest, and deploys production. Neither an agent nor CI performs live revision checks, firewall changes, DDL, or deployment. The earlier proposed production runner read-only connection is not selected under the human-only policy.

The human may execute reviewed local scripts, but the agent must not run them against Azure or trigger an Azure-affecting workflow. Migration files remain human-managed; no agent-authored revisions or automatic downgrade/reset are allowed.

## Release and rollback procedure

1. Develop on topic branches and merge into `main`; CI prepares artifacts and a human chooses when to deploy staging.
2. Prepare `release/x.y.z`; its updates run CI only. Make schema changes backward-compatible with the currently running API and frontend where needed.
3. Create the protected `x.y.z` tag on the validated release commit. The tag prepares a staging release candidate. A human may later deploy a newer `main` candidate over staging.
4. For a coordinated API/frontend change, the human migrates production, deploys a backward-compatible API, then deploys affected frontends by their own selected tags. Record the version tuple; the three version numbers need not match.
5. Verify API responsiveness, sign-in/token refresh, representative booking behavior, and authorized file access using controlled test data. Do not treat `/healthz` as a full readiness test.
6. On an application regression, select the previous compatible API digest/frontend artifact. Recheck schema and API contract compatibility first. Do not automatically downgrade the database.

Use a separate database recovery procedure for destructive data mistakes; application rollback is not a substitute for restoring data. After a restore, validate data and handle bookings, expiry work, and notifications produced since the restore point before reopening writes.

## Monitoring, recovery, and spending controls

- Email the primary operator. No overnight immediate-response commitment is made.
- Preserve the existing Sentry production `/healthz` uptime and Pending-payment expiry cron-monitor decisions. `/healthz` checks HTTP response only; cron success requires lock acquisition, completed work, and transaction commit. Validate actual Sentry account entitlements before activation.
- Use Azure infrastructure metrics for persistent resource/storage problems. Keep logging volume and retention deliberately bounded; do not export unsanitized application bodies or duplicate the entire Sentry pipeline into another paid backend.
- Targets measured from response start: application rollback within 30 minutes; database recovery within four hours. Database recovery-point objective: 15 minutes. Database backups and Blob soft-delete protection: 14 days. Validate restore and rollback before launch and periodically thereafter. Region failure has a separate procedure without the same initial recovery-time target.
- Proposed budget notifications for final review: annual grant-use thresholds at 75%, 85%, and 95%, plus a forecast-over-budget alert. Include all grant-funded subscription resources, not only the new apps. These are alerts, not an enforced cap, and billing data is delayed.
- Before exhaustion, reduce staging expenditure first, then arrange a user-approved production pause if necessary. Stopping a Web App does not stop its Plan charge; stopping PostgreSQL leaves storage/backup charges and automatically restarts compute after seven days. Cost reduction must be modeled per resource, preserving data, rather than assuming a generic stop action makes everything free. Grant expiration and any account-level spending limit need a separate pre-expiry check.

## Budget basis (Canada East history)

Indicative Canada East USD PAYG estimate, researched on 2026-11-09/10, using 730 hours/month and no reservations. Figures are planning inputs, not an Azure quote or proof of service/grant eligibility.

The itemized inventory in [`infra/azure/cost/`](../infra/azure/cost/README.md) supersedes the table below. With Private Endpoints removed and prices rechecked for Canada Central on 2026-11-12, it gives about USD 127.48/month (USD 1,530/year) before tax and other grant spend; it also adds further variable charges and does not apply shared free allowances.

| Item | Monthly USD assumption |
| --- | ---: |
| Two Linux B1 App Service Plans | 26.28 |
| Two PostgreSQL B1ms servers, each 32 GiB | 38.62 |
| Managed Redis Balanced B0, three nodes total | 37.23 |
| Two Standard and two Free Static Web Apps | 18.00 |
| Shared ACR Basic | 5.07 |
| Four Private Endpoints | 29.20 |
| Two shared Private DNS zones | 1.00 |
| Small illustrative Blob, Key Vault, additional public DNS query usage | 0.44 |
| Existing public DNS zone base charge, if charged to this grant | 0.50 |
| **Illustrative baseline** | **156.34** |

The baseline is approximately USD 1,876/year, leaving about USD 124/year before further usage. The small-use row assumes 10 GB live plus 2 GB soft-deleted Blob data, 10k writes/100k reads/10k other Blob operations, 20k Key Vault operations across both vaults, and 100k additional public DNS queries. These are examples to replace with measured usage, not quotas.

Logs, Private Link data processing, excess backup/retained versions, Private DNS queries, bandwidth beyond available allowances, metric alert charges, CI/package usage, and tax are not comprehensively included. For illustration, adding 1 GB/month of charged Analytics Logs at USD 2.76 and 5 GB/month of charged North American internet egress at USD 0.435 moves the estimate to roughly USD 159.53/month (USD 1,914/year), before other variable charges. Do not assume free allowances are unused elsewhere. Sentry account charges, if any, are outside the Azure grant and require their own check.

The rejected two-environment Container Apps estimate was about USD 210/month after its custom-VNet managed Public IP and Load Balancer costs were included. Earlier approximate USD 145-160 Container Apps estimates omitted those costs and are not valid complete budgets. App Service removes those particular Container Apps resources; it does not remove the four Private Endpoints.

Final budget acceptance requires live calculator/account verification and a credible forecast within the remaining grant. If testing requires larger plans/SKUs or forecast usage exceeds the grant, revisit sizing/staging expenditure before provisioning those changes. No self-funded excess is implied by accepting this architecture.

## Delivery sequence and acceptance gates

The agent delivers offline-validated code/templates/CSV/runbooks for these stages. Every actual Azure command, inspection, deployment, drill, and cleanup below is human-owned and stays pending until operator evidence is recorded.

1. **Account checks and prerequisites:** verify grant/expiry/spending controls, existing DNS and permissions, Canada Central capacity and SKU support, the supported Static Web Apps resource region, Sentry entitlements, package access, and Entra registrations/redirects. Confirm which resources already consume the grant.
2. **Application readiness:** fix/verify the current container entrypoint (it refers to `gunicorn_conf.py`, absent in the inspected checkout), constrain Docker build context with `.dockerignore`, test database/Redis TLS over public endpoints, adapt Redis single-database usage, verify HTTPS staging links, and disable production mock login. Existing auth/Redis failure behavior needs its own focused readiness review; do not promise immediate access-token revocation solely because a blacklist provider exists.
3. **Infrastructure:** implement Bicep by repository, review `what-if` and costs, bootstrap identities/secrets, create staging first, and validate connections from the real App Service container. Keep production resources gated on the account and budget checks.
4. **Staging release package:** implement non-Azure CI/build, immutable artifacts, and offline/mocked checks for the human-run source-map, migration/IP cleanup, serialization, smoke, and tag/main procedures. Test a failed migration, interrupted firewall cleanup, older-tag/newer-schema case, and application rollback.
5. **Recovery and capacity:** exercise PostgreSQL restore, Blob recovery, App Service restart/Always On behavior, Redis loss/failover and reconnects, and representative booking load. Validate B1/B1ms and Redis memory headroom; adjust the budget if capacity must change.
6. **Production:** configure domains/TLS, alerts and spending notifications; run the manual migration and tag deployment procedure; verify the end-to-end workflows and record the initial version tuple.

This planning change creates no Azure resources or live account sessions. Agents may later author implementation artifacts and offline tests, but all Azure operation and live verification remain exclusively human-run.

## Primary references

- [App Service plans](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans), [Linux pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/), [VNet integration](https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration), [Always On](https://learn.microsoft.com/en-us/azure/app-service/configure-common#configure-general-settings).
- [PostgreSQL Private Link](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private-link), [public networking](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-public), [backup/restore](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/postgresql/calculator/?culture=en-us&currency=USD).
- [Managed Redis tier/capacity](https://learn.microsoft.com/en-us/azure/redis/plan-tiers-and-capacity), [Private Link](https://learn.microsoft.com/en-us/azure/redis/private-link), [migration differences](https://learn.microsoft.com/en-us/azure/redis/migrate/migrate-basic-standard-premium-understand), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/managed-redis/calculator/?culture=en-us&currency=USD).
- [Static Web Apps plans](https://learn.microsoft.com/en-us/azure/static-web-apps/plans), [custom domains](https://learn.microsoft.com/en-us/azure/static-web-apps/custom-domain), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/app-service/static/calculator/?culture=en-us&currency=USD).
- [Private Link pricing](https://azure.microsoft.com/en-us/pricing/details/private-link/), [DNS pricing](https://azure.microsoft.com/en-us/pricing/details/dns/), [ACR pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/), [Storage pricing inputs](https://azure.microsoft.com/api/v3/pricing/storage/calculator/?culture=en-us&currency=USD), [Key Vault pricing](https://azure.microsoft.com/en-us/pricing/details/key-vault/), [Monitor pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/), [bandwidth pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/).
- [Azure region/AZ list](https://learn.microsoft.com/en-us/azure/reliability/regions-list), [Bicep overview](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview), [GitHub Azure OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure), [budget behavior](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets), [Container Apps managed resources](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks#managed-resources).
