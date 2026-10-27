# Sentry observability boundaries

## Status

Accepted on 2026-10-27 after the user confirmed the final scope. This ADR records the agreed design; SDK implementation has not started.

Published specification: [Core API #258](https://github.com/efcnewlife/newlife-core-api/issues/258), synchronized as [EFC-277](https://linear.app/jayhsia/issue/EFC-277/spec-sentry-sdk-integration-across-newlife-applications).

## Confirmed decisions

The design covers `newlife-core-api`, `facility-booking-frontend`, and `newlife-portal-frontend`. Implementation work remains repository-scoped.

The first implementation phase is limited to SDK integration, data sanitization, and release/environment configuration, with verification of those changes. This supersedes the earlier broader first-phase proposal. SDK integration covers Error Monitoring, sanitized logs/breadcrumbs, basic tracing using OpenTelemetry, and masked browser Replay. Account provisioning, CI/deployment work, source-map upload, upload failure gates, and uptime/cron monitor activation are deferred.

The outcome priorities, in order, are error diagnosis and impact assessment, detecting regressions after deployment, actionable service or scheduled-work notifications, and reproducing the user's interaction context.

Use Sentry Cloud. Enable collection in `stg` and `prod`; disable it by default in `dev`, with explicit opt-in for verification. Staging must not trigger production notifications.

Create one Sentry project per application. Use the same lowercase telemetry environment vocabulary (`dev`, `stg`, `prod`) across all three repositories. Frontend build mode and runtime optimization flags are separate concerns: map `development` to `dev`, `staging` to `stg`, and `production` to `prod` at the telemetry boundary, without changing production build optimization semantics. Validate automated-test and unknown-mode handling during implementation to prevent accidental telemetry export or production mislabeling.

Use OpenTelemetry as the instrumentation standard, preserving a future integration path to Azure Monitor Application Insights. Azure export is future work, not part of this integration. Avoid duplicate providers, instrumentation, and spans when composing Sentry with OpenTelemetry; the exact SDK bridge must be verified.

Start on the free Sentry Developer plan. Do not enable paid services or treat temporary trial capabilities as permanent entitlements. The SDK feature scope is subject to free-plan capabilities and quotas.

Use email notifications for the first phase. Use Sentry's default notification behavior; do not create custom alert rules, notification intervals, thresholds, or recipient routing as part of this integration. Defer Teams integration; the user prefers to avoid its additional setup.

The user requested staging integration without a separate quota-planning exercise. Sampling and volume tuning are deferred for this phase; this supersedes the earlier proposed production percentages and error-session-only Replay policy. This is not authorization for blanket 100% collection or relaxed sanitization.

Telemetry failure or exhausted quotas must not block login, Booking, or other application work. Do not automatically upgrade the plan or create an unbounded retry queue.

Do not add custom quota management, volume caps, sampling optimization, or a mandatory budget-configuration step. Keep the SDK collection controls configurable. Where a feature requires an explicit enablement or sampling option, use a documented minimal integration configuration during implementation and report what is actually enabled; omitted options must not be described as active features. No production/staging sampling percentages are fixed by this ADR. Collect only sanitized warning/error logs. Free-plan limits still apply, and temporary trial capabilities must not become dependencies.

Expected business rejections and ordinary 4xx responses do not create Sentry issues. Collect unexpected exceptions, 5xx failures, and background-work failures. Report the same failure once rather than through duplicate explicit capture and log capture paths.

Use `<repo>@<version>` as the Sentry release identifier, with production semantic versions such as `newlife-core-api@0.2.33`, staging short commit hashes such as `newlife-core-api@5ba2c79`, and `newlife-core-api@local` for opted-in local development. Each repository versions independently. The SDK, CI release creation, and source-map upload must use the exact same release value for a given build. This retains the environment-dependent version convention shown in the user's `conf-portal-api` reference screenshot while preventing independent repository releases from sharing a Sentry release accidentally.

None of the three applications is deployed yet. Azure is the intended future hosting platform; the Azure service and deployment pipeline are not yet established by this interview. Do not copy TheHope's deployment provider or assume live URLs or existing Azure resources.

Defer deep performance analysis, Profiling, and custom business metrics.

User identity sent to Sentry is limited to an internal ID without name or email. This ceiling allows affected-user correlation while reducing direct identity disclosure. Exclude request and response bodies, passwords, tokens, names, email addresses, phone numbers, and remarks. Apply sanitization to URLs, logs, and breadcrumbs as well. Mask replay text and inputs, and block images and video by default. Detailed filtering and verification cases remain to be designed.

The user identified `TheHopeTechTeam/conf-portal-api` as a reference implementation to inspect. Its configuration is reference evidence, not an adopted design or an instruction to copy its collection policy.

## Confirmed decisions for deferred deployment work

- Allocate the initial uptime monitor to production Core API's existing `/healthz`. This endpoint verifies HTTP responsiveness only; it does not check DB, Redis, Booking readiness, or background-work health. No readiness redesign is included.
- Allocate the sole cron monitor to the production Pending-payment expiry sweep. Only an execution that acquired the lock, completed the sweep, and committed its database transaction reports success. Lock contention is not a failed execution and must not manufacture a success check-in. Notification-email failure is reported separately as an error. Preserve the existing interval loop and account for its execution duration and multi-process lock behavior when designing check-ins; do not introduce a new scheduler.
- Failure to upload required frontend source maps blocks deployment of the new build; the running version continues serving. This build/deployment gate is distinct from runtime telemetry failures, which must not block application work.

These policies are recorded for future deployment work and do not authorize implementing monitors or deployment pipelines in the current SDK phase.

## Implementation verification obligations

- Verify automated-test/unknown-environment behavior; tests must not accidentally send real telemetry. Sampling tuning is deferred.
- Detailed sanitization and verification cases, including login and member-management surfaces. These are implementation verification obligations, not permission to weaken the agreed privacy policy.
- OpenTelemetry/Sentry composition and the minimum options required to activate each agreed SDK feature, to be verified against supported SDK versions during implementation.

Account region, retention, entitlements, source-map/release API access, deployment URLs, and Azure activation remain future provisioning checks. Email alert rules and routing are deliberately outside implementation scope.

## Plan and notification evidence

Checked on 2026-10-27: [Sentry pricing](https://sentry.io/pricing/) lists Developer as one user with unlimited projects, 5,000 errors, 5 million spans, 50 replays, 5 GB logs, one uptime monitor, and one cron monitor. These are plan allowances, not per-project allocations; actual account entitlements remain unverified. Third-party integrations are listed under Team. Do not rely on introductory Replay promotions for steady-state design.

[Sentry's release API documentation](https://docs.sentry.io/api/releases/create-a-new-release-for-an-organization/) states that matching release versions in multiple projects within an organization are treated as the same release. Project separation therefore does not provide a release namespace.

For a future Teams integration, prefer a Standard channel in a Team whose membership is appropriate for operational alerts. A Private Team can restrict membership while retaining a Standard channel. [Microsoft documents](https://support.microsoft.com/en-us/teams/teams-channels/use-apps-private-channels-microsoft-teams) that Private-channel app support depends on the app and requires per-channel installation; the [Sentry installation guide](https://docs.sentry.io/integrations/notification-incidents/msteams/) does not establish Private-channel compatibility. Channel choice is still a recommendation, not a confirmed user decision.

## Current implementation evidence

Local inspection found no Sentry dependency in the three application manifests. Core's `portal/route_classes/log_route.py` logs request bodies and unfiltered response bodies; forwarding existing logs therefore needs an explicit sanitization policy before enabling collection. These findings do not establish deployed configuration or Sentry account state.
