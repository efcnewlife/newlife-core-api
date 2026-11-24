# Additive Azure Monitor observability

## Status

Accepted on 2026-11-24 after the user confirmed the consolidated design and frontend collection scope. SDK composition and live acceptance evidence remain implementation obligations, not proven capabilities. This interview accepts the design; implementation and provisioning have not been requested or performed.

Published specification: [Core API #320](https://github.com/efcnewlife/newlife-core-api/issues/320), synchronized as [EFC-350](https://linear.app/jayhsia/issue/EFC-350/spec-additive-azure-monitor-observability-across-newlife-applications), in the `newlife core api` project with `spec` and `ready-for-agent` labels and Backlog status at publication.

## Confirmed direction

Retain Sentry and evaluate Azure Monitor / Application Insights as complementary observability for both React applications, Core API, and its PostgreSQL, Redis, and Azure Blob Storage dependencies. Frontend hosting remains Cloudflare Workers Static Assets. Value priorities are platform health and resource visibility, API/dependency performance, then browser-to-dependency investigation.

The delivery scope includes both frontends and the backend dependencies together. Validate the complete chain in staging before enabling the production scope; a backend-only result does not complete delivery.

Use USD 10 per month as the initial overall incremental Azure monitoring budget target, superseding the initial free-allowance-only constraint. The user expects low ingestion volume; this is not a measured volume estimate or a guaranteed billing ceiling. Use a monthly Azure Subscription-scope budget filtered to the incremental monitoring resources, with actual-cost email notifications at 80% and 100% and a forecast-cost email notification at 100%. Do not automatically stop services or monitoring. If the billing currency is not USD, configure the corresponding billing-currency amount. Recipients are to be explicitly supplied at provisioning. Available free allowance has not been verified for the account.

Keep Sentry's existing notification behavior unchanged. Do not add or change Sentry monitors or notifications, and do not add Azure proactive operational notifications; the user will inspect Azure manually. Budget/Cost alerts are the explicitly accepted exception. Do not introduce Azure-to-Sentry alert forwarding. Platform-only failures are not guaranteed to produce a notification under this decision.

## Collection and retention

Initially configure tracing at 100% in staging and production across the two browser applications and Core API, retaining separate configurable environment settings. This is a source collection policy, not a guarantee that every operation survives browser blocking, transport failure, quotas, or throttling. Preserve the agreed INFO-and-higher Azure application-log policy independently of trace sampling.

Retain Application Insights telemetry for 90 days, without additional long-term archive or export. Business audit data remains governed by its existing policy.

Include existing background work, including Pending-payment expiry, mail dispatch, and EventBus handlers, with spans, dependencies, and application logs. Standalone work has its own trace; retain valid causal links where available without inheriting stale request identity. Do not fabricate an HTTP parent or add a scheduler/monitor.

## Resource isolation

Use separate Log Analytics workspaces for staging and production. Within each environment, use separate Application Insights resources for browser telemetry and Core API telemetry; distinguish Portal and Booking by stable application role names. This yields four Application Insights resources and two workspaces. Verify cross-resource correlation and map discovery. Billing-account free allowances remain shared rather than multiplied by resource count.

## Platform overview and dependency diagnostics

Deliver a NewLife Azure Workbook with environment and time-range filters. Combine available App Service platform-health and resource metrics, PostgreSQL/Redis/Blob standard metrics, API call volume/p95 latency/failure rate, dependency performance, and recent warning/error application logs. Link to Application Map, complete log queries, and Cost Management. Use metrics actually supported by the deployed resource types and tiers, and distinguish platform metrics from client-observed dependency timings. Do not fabricate an availability measurement from the absence of logs or requests.

The initial dependency diagnostic scope is client dependency spans, standard platform metrics, and Core API application logs. Do not enable detailed PostgreSQL server/query logs, Redis diagnostic logs, or Storage access logs in this delivery. Their addition requires a later, specific diagnostic need and cost/privacy review. This scope does not promise database-internal query analysis.

## Provisioning and ownership

Own monitoring resource definitions, Workbook content, and budget configuration in `newlife-infra` using Bicep and version-controlled configuration. Application repositories own SDK integration and environment configuration contracts. Human operators execute provisioning and supply deployment-specific values such as resource IDs and email recipients. Azure Portal remains the everyday investigation interface; a new automated deployment platform is outside this delivery.

## Confirmed acceptance boundaries

Validate actual Core API dependency calls to PostgreSQL, Redis, and Blob in Application Map, including call volume, duration, and failure rate. Separately validate distinguishable Portal and Booking browser telemetry correlated through Core API to dependencies in transaction details. A fixed map layout with two separate browser circles is not required. Only actual calls belong in the map; generating a Blob SAS URL locally is not evidence of an API-to-Blob network call.

Include explicit instrumentation for a small selection of critical business operations rather than treating automatic page views and requests as coverage of every user interaction. The accepted minimum scenarios are Portal login and administrator booking modification, Booking login and booking submission, plus supplementary scenarios that actually exercise PostgreSQL, Redis, and Blob, including controlled slow calls and failures. Not every business flow must exercise all three dependencies.

Verify browser-operation-to-API correlation, real dependency telemetry, absence of duplicate records within each destination, privacy sanitization, and continued business operation when Azure telemetry delivery fails. Detailed test steps remain to be specified.

Under the same staging container specification and representative load, compare telemetry disabled and enabled. API p95 latency increase must not exceed max(10 ms, 10% of the disabled baseline). Apply the same gate when an exporter cannot connect, and verify no continually growing queue or memory usage. Browser telemetry must not block operation completion, and failure of one destination must not disable the other. Define a reproducible workload and measurement window before running the acceptance benchmark.

Block the overall production delivery if any required capability fails staging verification, including Sentry Profiles, either frontend's correlation, shared trace IDs, or dependency coverage. Bring concrete evidence back for a design decision rather than silently dropping a capability or declaring partial delivery complete.

## Application logs and cross-vendor correlation

Include Core API application logs in Azure at INFO and higher severity, subject to the existing privacy requirements. The user selected all application INFO-and-higher logs rather than a curated subset of INFO messages. This does not change Sentry's existing log collection or notification policy. Retain App Service Log stream for immediate container/startup investigation. Logger wiring and quantitative volume remain to be specified.

Both frontends send browser telemetry to their environment's browser Application Insights resource: page loads, SPA navigation, selected critical operations, and Core API request timing/results/correlation. The INFO-and-higher application-log decision applies to Core API; wholesale browser console-log export is not included. Sentry Replay and existing notifications remain in place.

Apply ADR 0038's agreed privacy ceiling to both export paths, including automatic spans and logs: no request/response bodies, credentials, personal fields, remarks, SQL parameters, Redis keys/values, or Blob SAS tokens. Retain only permitted sanitized query structure, URLs, and attributes. Verify each payload category rather than assuming Sentry event sanitizers also cover OpenTelemetry or OTLP payloads.

Target a shared native trace ID across Sentry and Azure for the same retained operation. Identical span sets or span IDs in both destinations are not required. Verify this while preserving existing Sentry capabilities and notification behavior; surface any conflict with the separately agreed profiling design before accepting a compromise.

## Selected tracing direction

The user selected unified Core API OpenTelemetry instrumentation with export to Sentry and Azure, rather than maintaining two independent tracing implementations. Preserve the existing `distributed_trace` / `TraceSpan` application interface and implement the OpenTelemetry adaptation underneath it. One process-wide tracing composition owns span creation and context; destination-specific exporters own delivery. Sentry retains its SDK-specific error, log, and profiling responsibilities, subject to compatibility verification. This direction does not require one vendor-neutral exporter for every telemetry signal.

The current implementation still creates Sentry-native spans. Verify the unified direction against pinned SDK versions, including preservation of Sentry Profiles, error/log correlation and deduplication, sanitization before either export, and independent destination failure handling. Do not assume native profiling lifecycle behavior carries over to OTLP export. Any necessary compromise remains a user decision.

The two frontends continue to require browser SDK integration and explicit context/propagation ownership; selecting backend OpenTelemetry does not establish a unified browser pipeline. Validate the complete frontend/backend/dependency chain and Sentry compatibility in staging before the production delivery. Detailed exporter selection and browser context coordination remain open.

## Superseded architecture decisions

This ADR supersedes [ADR 0038](0038-sentry-observability-boundaries.md) where it requires mutually exclusive Sentry/Azure backends and Sentry-native Core API tracing ownership. One tracing composition with multiple export destinations replaces that restriction in the accepted design. The agreed collection rate is expressed through the selected OpenTelemetry composition rather than requiring simultaneous Sentry-native tracing configuration. Existing code still follows the earlier contract and needs implementation changes. Preserve ADR 0038's Sentry capability, privacy, error deduplication, profiling, and notification requirements except where explicitly revised here; any incompatible capability blocks delivery and returns for a user decision.

## Evidence and open acceptance boundaries

- [App Service Python autoinstrumentation](https://learn.microsoft.com/en-us/azure/azure-monitor/app/codeless-app-service) does not support custom containers. Code-based instrumentation is required for this deployment.
- [Application Map](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-map) is derived from recorded telemetry. The agreed browser correlation and dependency map criteria require real ingestion evidence.
- [Azure Monitor pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/) describes shared billing-account free ingestion allowances; their remaining availability has not been verified for this account.
- [Daily caps](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/daily-cap) can overshoot and excess ingestion is still billed. A daily cap does not guarantee an exact USD 10 monthly maximum.

The remaining work is technical verification and implementation detail: pinned SDK/exporter compatibility, browser context ownership, asyncpg/Redis/Blob instrumentation and deduplication, preservation of Sentry Profiles, payload sanitization, reproducible benchmark procedures, real cross-resource ingestion/map evidence, and deployment-specific values. These must be resolved within the agreed scope; any required capability that cannot be preserved blocks production delivery and returns for an explicit design decision. No live Azure or Sentry account state or deployed telemetry has been verified.
