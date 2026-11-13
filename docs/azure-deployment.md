# Azure deployment plan

Design assembled on 2026-11-10 and revised on 2026-11-13 through [EFC-322](https://linear.app/jayhsia/issue/EFC-322). Decisions are recorded in [ADR 0039](adr/0039-azure-deployment-and-release-direction.md) and the [EFC-291 spec](https://linear.app/jayhsia/issue/EFC-291). This document describes the selected deployment direction; it does not report provisioned Azure resources or implemented pipelines.

The selected flow automatically publishes and deploys `main` and eligible tags to staging using GitHub OIDC. Both environments retain manual migrations and image rollback. Staging deploys first and the operator migrates afterward; production migrates first and the operator then deploys the verified tag manually. CI migration was considered and rejected because runner database access and firewall cleanup add unnecessary operational complexity for this application.

## Mandatory execution boundary

Agents may author and review Bicep, source code, CSV estimates, workflow definitions, operator scripts, documentation, and offline tests only. Agents must not sign in to Azure, inspect the live account, run Azure what-if/apply, create/update/delete resources, change DNS/RBAC/secrets/firewalls, push/pull images through ACR, deploy apps, run migrations against Azure databases, restore data, or trigger Azure-affecting workflows. Public documentation/pricing research and local tests without live Azure access are allowed.

After human setup, application workflows may use scoped GitHub OIDC federation for artifact publication and automatic staging deployment. Do not store a long-lived Azure client secret or grant production deployment, database migration, or infrastructure administration access to these workflows. Provisioning, federation/RBAC/secret/DNS/firewall setup, database operations, production deployment, recovery, and rollback remain human-operated. CI must not obtain migration credentials, inspect live database revisions, or create runner database firewall rules. Human execution and live verification must be explicitly attributed and must not be claimed complete without operator-supplied evidence. This document change enables no automation and authorizes no agent Azure session.

## Scope and constraints

- Host Core API, Newlife Portal, and Facility Booking for approximately 200 users with low expected concurrency.
- Use Canada Central (Toronto) for regional resources. On 2026-11-12 the operator found PostgreSQL provisioning restricted in Canada East for the grant subscription, so the earlier Canada East choice is superseded (see [ADR 0039](adr/0039-azure-deployment-and-release-direction.md)). Validate each SKU, quota, and capacity before provisioning; Canada Central support for PostgreSQL 18 `Standard_B1ms`, Managed Redis `Balanced_B0`, and Linux App Service `B1` is a pending human check. Canada Central has Availability Zones, but this plan does not change the HA choices; whether production Redis HA spreads its nodes across zones is not part of the plan or the estimate. Staging has two East US 2 placement exceptions, Managed Redis (no capacity) and the API App Service (no `B1` quota), recorded in ADR 0039.
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

Revision 2026-11-13 ([EFC-308](https://linear.app/jayhsia/issue/EFC-308)): all Azure infrastructure lives in [`efcnewlife/newlife-infra`](https://github.com/efcnewlife/newlife-infra), the only editable source ([newlife-infra ADR 0001](https://github.com/efcnewlife/newlife-infra/blob/main/docs/adr/0001-newlife-infra-owns-azure-infrastructure.md)). This supersedes the earlier proposal of an `infra/azure/` directory in each application repository. Templates are in `azure/modules/`, shared-registry parameters in `azure/shared/`, and per-environment parameters in `azure/environments/<env>/`; see the [registry runbook](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-container-registry.md) and the [staging API runbook](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-staging-api.md).

| Repository | Owns |
| --- | --- |
| `newlife-infra` | Bicep and parameters for API apps/plans, PostgreSQL and its firewall allowlist, Redis, Blob, Key Vault, shared ACR, Portal and Booking Static Web Apps, domain bindings and DNS records, backend monitoring; cost estimate; Bicep validation and tests; infrastructure runbooks |
| `newlife-core-api` | API source, Dockerfile, image build and local smoke, [image publication](azure-container-registry.md), configuration contract, Alembic revisions, application CI, this spec and ADR 0039 |
| `newlife-portal-frontend` | Portal source, builds, frontend workflows |
| `facility-booking-frontend` | Booking source, builds, frontend workflows |

Keep Bicep modules reusable, with environment-specific parameters. Reference the existing public DNS zone; do not recreate or transfer it. Data services and credentials remain separate per environment.

Infrastructure delivery: the agent authors and offline-validates Bicep and operator procedures. The human runs Azure `what-if`, reviews changes/costs, and applies them. Infrastructure CI does not apply changes. Application workflows may publish artifacts and deploy staging using scoped OIDC federation. Humans establish operator/runtime identities and workflow federation/RBAC, documenting actual permission boundaries. Agent-run cloud inspection is prohibited.

## Domains and connections

| Application | Production | Staging |
| --- | --- | --- |
| Core API | `api.efcnewlife.com` | `api.dev.efcnewlife.com` |
| Portal | `portal.efcnewlife.com` | `portal.dev.efcnewlife.com` |
| Booking | `booking.efcnewlife.com` | `booking.dev.efcnewlife.com` |

Here `dev` means staging, not local development. Configure exact HTTPS origins consistently in frontend builds, API CORS/member-app settings, Entra redirect URIs, and email/application links. Bind managed certificates to the full hostnames and verify the existing DNS/CAA configuration.

- API ingress is public HTTPS. The user removed Private Endpoints, Private DNS zones, and VNet integration on 2026-11-10 to save about USD 31/month; see the [cost estimate](https://github.com/efcnewlife/newlife-infra/blob/main/azure/cost/README.md).
- PostgreSQL uses `Public access (allowed IP addresses)`. The firewall allows every App Service possible outbound IP plus explicit developer/operator IPs, with TLS required. Those outbound IPs are shared with other customers on the same deployment unit and can change, so re-check the list after scaling. Do not enable the all-Azure-services rule or unrestricted public access.
- Managed Redis has no IP allowlist, so both instances use public access from all networks, protected by access keys or Entra authentication and TLS. Sharing one instance between staging and production is under consideration, not selected.
- Blob endpoints remain reachable by external browsers for authorized/SAS URLs, with anonymous access disabled. Use Hot/LRS without hierarchical namespace, 14-day soft delete, and a 10 GB first-year live-data estimating assumption. There is no initial video workload.
- ACR Basic and Key Vault can use authenticated public endpoints initially. Use image-pull identity/RBAC and Key Vault references where supported; application secrets stay out of Git and frontend builds. The existing Blob adapter still uses connection-string/account-key SAS, so do not assume application-level managed identity conversion is already implemented.
- No Private Endpoint, NAT Gateway, permanent administration VM, VPN Gateway, or Container Apps environment is included.

## CI and deployment events

| Event | CI | Staging | Production |
| --- | --- | --- | --- |
| Pull request | Repository checks, tests, build validation | No privileged deployment by default | None |
| Update `main` | Required checks and exact-commit build | Automatic publication and deployment | None |
| Update `release/x.y.z` | Required checks only | None from the branch event | None |
| Create eligible `x.y.z` tag | Verify release commit/CI and build tagged source | Automatically publish and deploy the exact tag | None |
| Human production release selecting tag | Review artifacts and that exact tag's completed staging acceptance | Need not still run this tag | Human migrates first, then deploys the verified artifact |

Feature/fix branches merge into `main` through reviewed PRs. Staging normally tests `main`; create `release/x.y.z` from a selected, verified `main` commit to prepare production. Tags have no `v` prefix, for example `0.3.0`, and identify CI-passing release-branch commits. Protect release tags against movement/deletion. Each of the three application repositories versions independently; shared UI package and infrastructure publication have separate procedures.

There is no staging source-switch mode or release freeze. A later `main` update may automatically deploy over a tagged staging version. Production always uses the selected tag's immutable commit/artifact mapping and requires recorded acceptance of that exact tag after required manual staging migration; passing a `main` run alone is insufficient. Neither creating the tag nor completing its workflow deploys production.

Serialize backend deployment/migration operations per environment. Do not cancel a running migration just to deploy a newer commit. Queue later deployments and retain the exact run/commit identity. Determine compatibility before applying or deploying an older tagged version against a newer staging schema; block unknown or incompatible cases without downgrade or data reset.

### Core API artifacts

For `main` and eligible tag events, required CI builds the exact source commit, records its full SHA, publishes the image to ACR, and deploys staging. Use scoped OIDC federation for Azure login and retain the commit/tag-to-digest mapping and rollback images. Release image tags must not be overwritten. The human production release changes the App Service image tag to the verified release image and confirms its digest mapping, rather than rebuilding an image or taking whatever currently runs on staging. Runtime settings and Sentry environment/release values can differ per environment.

OIDC/RBAC definitions and operator setup belong in `newlife-infra`; application workflow definitions remain in this repository. The operator creates the federation and scoped permissions. Build/publication and staging deployment receive only the permissions they need, without database or production deployment access.

Validate the container entrypoint, listening port, and App Service container configuration. Set Always On; Basic has no deployment slots, so allow for a restart/interruption and do not promise slot-swap or zero-downtime deployment. Preserve the existing Pending-payment expiry interval loop and locking behavior.

### Frontend artifacts

Use pnpm with the committed lockfile, package-read authentication for `@efcnewlife/newlife-ui`, type checks, relevant tests, and production/staging builds. API URLs and MSAL/Sentry settings are build-time inputs: build distinct environment artifacts from the same tagged source when needed. Do not promote staging `dist` unchanged to production when it embeds staging endpoints.

The publishing procedure creates and uploads required source maps using the exact Sentry release ID used by that build, whether the publication is automated staging or manual production. Source-map upload failure blocks publishing the new build while the running website remains available. Preserve [ADR 0038](adr/0038-sentry-observability-boundaries.md): `<repo>@<short-commit>` for staging and `<repo>@<version>` for production. Keep Sentry auth tokens and package tokens in CI secrets, never `VITE_*`. Frontends follow the same main/release/tag flow, but publish to Static Web Apps rather than ACR/App Service; detailed production publication remains existing frontend release work.

Configure SPA navigation fallback and explicit cache behavior so direct links work and an old HTML entry point does not strand users on unavailable assets. Keep previous deployable artifacts for rollback. Smoke-test HTTPS, a deep link, login, and API connectivity after deployment.

## Migrations

Migration files remain human-managed; agents must not add, modify, or delete files under `alembic/versions/`.

Both environments use a human operator's exact target checkout with `uv sync --frozen` and `uv run alembic upgrade head`. Runtime images continue to exclude Alembic files; no migration image or CI migration runner is selected. The operator manually runs `init-all` after the first successful schema migration, including its interactive superuser step. Catalog bootstrap is not part of a deployment workflow.

### Staging: human-executed

1. Successful `main` or eligible tag CI publishes the image to ACR and automatically deploys staging. Record the deployed full SHA, tag where applicable, and image digest. Initial deployment/smoke results are reported without automatic image rollback. Staging may temporarily fail while a required migration is pending; a passing initial smoke check is not final release acceptance in that case.
2. The human checks out the exact deployed version, reviews cost/account prerequisites, current revisions, and compatibility, and coordinates the manual work with other staging deployments. The human adds their exact public IP to PostgreSQL if necessary and verifies TLS connectivity; firewall propagation may require bounded retries. Runner database access is not needed.
3. The human runs that target version's committed migrations, checks the exit status and resulting revisions, and removes any temporary rule they created. The human audits residual temporary rules without deleting unrelated developer rules.
4. The human performs smoke and functional verification after required migration and records the exact version/revisions/result. A failed staging migration blocks release acceptance and production publication, although the staging image is already deployed. If a later `main` deployment has replaced the tag, do not attribute that later version's checks to the tagged release; verify the exact tagged version before accepting it. Rollback is a manual decision, subject to image/schema compatibility.

### Production: human-executed

The human selects/checks out a tag whose exact version passed staging acceptance after required migration. Verify recovery and backward compatibility, read current revisions, and manually apply migrations over TLS from an allowlisted local IP. Migrations must remain compatible with the old image still running in production. A failed migration blocks the production image update. The human records the tag/revisions/result, changes the App Service image tag to the already-published and verified release image, confirms the digest mapping, and verifies production. Neither an agent nor CI performs production live revision checks, firewall changes, DDL, or deployment. No production deployment workflow or runner database connection is selected.

The human may execute reviewed local scripts, but the agent must not run them against Azure or trigger an Azure-affecting workflow. Migration files remain human-managed; no agent-authored revisions or automatic downgrade/reset are allowed.

## Release and rollback procedure

1. Develop on topic branches and merge into `main`; CI builds/publishes and automatically deploys staging. The operator manually migrates staging afterward when required and verifies that version.
2. Prepare `release/x.y.z`; its updates run CI only. Make schema changes backward-compatible with the currently running API and frontend where needed.
3. Create the protected `x.y.z` tag on the CI-validated release commit. Its workflow builds/publishes and automatically deploys that tag to staging. Complete required manual staging migration and verify the exact tag before accepting it for production. Later `main` updates may deploy over staging without changing the accepted tag or production selection.
4. For a coordinated API/frontend change, the human migrates production, deploys a backward-compatible API, then deploys affected frontends by their own selected tags. Record the version tuple; the three version numbers need not match.
5. Verify API responsiveness, sign-in/token refresh, representative booking behavior, and authorized file access using controlled test data. Do not treat `/healthz` as a full readiness test.
6. On an application regression in either environment, the operator selects the previous compatible API image/frontend artifact. Recheck schema and API contract compatibility first. Staging smoke failure reports the result without automatic image rollback, allowing the operator to complete pending migration and re-verify. Do not automatically downgrade the database.

For release fixes, open `hotfix/*` from the target release branch and merge the fix back through a PR. Publish the next patch tag, for example `0.3.0` to `0.3.1`, without moving the original tag. The new tag repeats staging deployment and acceptance before manual production publication. Synchronize every hotfix into `main` through a separate branch and PR so the next release retains the fix without bringing unrelated `main` changes into the current release.

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

The itemized inventory in [`newlife-infra/azure/cost/`](https://github.com/efcnewlife/newlife-infra/blob/main/azure/cost/README.md) supersedes the table below. With Private Endpoints removed and prices rechecked for Canada Central on 2026-11-12, it gives about USD 126.22/month (USD 1,514.66/year, after the 2026-11-13 staging East US 2 moves) before tax and other grant spend; it also adds further variable charges and does not apply shared free allowances.

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

The agent delivers offline-validated code/templates/CSV/workflows/runbooks for these stages. Human setup and live acceptance stay pending until operator evidence is recorded. After the operator establishes scoped federation and enables the application workflows, CI may publish artifacts and automatically deploy staging within the boundary above; the agent does not trigger those workflows.

1. **Account checks and prerequisites:** verify grant/expiry/spending controls, existing DNS and permissions, Canada Central capacity and SKU support, the supported Static Web Apps resource region, Sentry entitlements, package access, and Entra registrations/redirects. Confirm which resources already consume the grant.
2. **Application readiness:** fix/verify the current container entrypoint (it refers to `gunicorn_conf.py`, absent in the inspected checkout), constrain Docker build context with `.dockerignore`, test database/Redis TLS over public endpoints, adapt Redis single-database usage, verify HTTPS staging links, and disable production mock login. Existing auth/Redis failure behavior needs its own focused readiness review; do not promise immediate access-token revocation solely because a blacklist provider exists.
3. **Infrastructure:** implement Bicep in `newlife-infra`, review `what-if` and costs, bootstrap identities/secrets, create staging first, and validate connections from the real App Service container. Keep production resources gated on the account and budget checks.
4. **Staging release package:** implement application CI/build, immutable artifact mappings, scoped OIDC publication and automatic staging deployment for main/tag events, and offline/mocked checks. Cover source-map publication, per-environment serialization, manual post-deployment migration/verification, and manual rollback. Test failed CI/publication/smoke, failed human migration, operator IP-rule cleanup, and older-tag/newer-schema cases without giving CI database access. Carry this decision into existing release tickets, including [EFC-311](https://linear.app/jayhsia/issue/EFC-311); no new spec or implementation ticket is required.
5. **Recovery and capacity:** exercise PostgreSQL restore, Blob recovery, App Service restart/Always On behavior, Redis loss/failover and reconnects, and representative booking load. Validate B1/B1ms and Redis memory headroom; adjust the budget if capacity must change.
6. **Production:** configure domains/TLS, alerts and spending notifications; run the manual migration and tag deployment procedure; verify the end-to-end workflows and record the initial version tuple.

This documentation change creates no Azure resources, workflows, or live account sessions. Agents may later author implementation artifacts and offline tests. Artifact publication and automatic staging application deployment are the only selected CI Azure exception; infrastructure, database work, production rollout, and recovery remain human-operated. Record live acceptance separately from offline checks.

## Primary references

- [App Service plans](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans), [Linux pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/), [VNet integration](https://learn.microsoft.com/en-us/azure/app-service/overview-vnet-integration), [Always On](https://learn.microsoft.com/en-us/azure/app-service/configure-common#configure-general-settings).
- [PostgreSQL Private Link](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private-link), [public networking](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-public), [backup/restore](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/postgresql/calculator/?culture=en-us&currency=USD).
- [Managed Redis tier/capacity](https://learn.microsoft.com/en-us/azure/redis/plan-tiers-and-capacity), [Private Link](https://learn.microsoft.com/en-us/azure/redis/private-link), [migration differences](https://learn.microsoft.com/en-us/azure/redis/migrate/migrate-basic-standard-premium-understand), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/managed-redis/calculator/?culture=en-us&currency=USD).
- [Static Web Apps plans](https://learn.microsoft.com/en-us/azure/static-web-apps/plans), [custom domains](https://learn.microsoft.com/en-us/azure/static-web-apps/custom-domain), [pricing inputs](https://azure.microsoft.com/api/v3/pricing/app-service/static/calculator/?culture=en-us&currency=USD).
- [Private Link pricing](https://azure.microsoft.com/en-us/pricing/details/private-link/), [DNS pricing](https://azure.microsoft.com/en-us/pricing/details/dns/), [ACR pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/), [Storage pricing inputs](https://azure.microsoft.com/api/v3/pricing/storage/calculator/?culture=en-us&currency=USD), [Key Vault pricing](https://azure.microsoft.com/en-us/pricing/details/key-vault/), [Monitor pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/), [bandwidth pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/).
- [Azure region/AZ list](https://learn.microsoft.com/en-us/azure/reliability/regions-list), [Bicep overview](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview), [GitHub Azure OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure), [budget behavior](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets), [Container Apps managed resources](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks#managed-resources).
