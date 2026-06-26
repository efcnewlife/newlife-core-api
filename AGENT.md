# AGENT.md — AI Entry Guide for newlife-core-api

This document helps AI agents quickly understand the **NewLife Core API** codebase: architecture, conventions, and where to make changes. For diagrams and extended narrative, see [`README.md`](README.md). For enforceable coding rules, see [`.cursor/rules/standard.mdc`](.cursor/rules/standard.mdc).

---

## 1. What This Project Is

| Item | Value |
|------|-------|
| **Purpose** | Backend portal API for NewLife Core infrastructure — admin CRUD, RBAC, facility booking, org/ministry management |
| **Framework** | FastAPI (async) |
| **Database** | PostgreSQL 17 + SQLAlchemy (asyncpg) |
| **Cache** | Redis (auth blacklist, RBAC caches, rate limiting) |
| **Auth** | JWT (email/password + Microsoft Entra ID token exchange) |
| **Authorization** | RBAC — roles, permissions, resources, verbs |
| **DI** | `dependency-injector` |
| **Package manager** | Poetry (`poetry run …`) |
| **Python** | 3.14+ (see `pyproject.toml`) |
| **Migrations** | Alembic — **agents must not add/modify/delete files under `alembic/`** |

### Related repositories

| Repo | Role |
|------|------|
| `newlife-portal-frontend` | Admin SPA; consumes `/admin/api/v1/*` |
| `newlife-ui` | Shared React component library for the portal |
| `facility-booking-frontend` | Facility booking consumer (if applicable) |
| `newlife-docs` | Product / process documentation |

---

## 2. Quick Commands

```bash
# Install
poetry install

# Local infra
docker compose up -d

# DB migrate
poetry run alembic upgrade head

# Dev server
poetry run uvicorn portal.main:app --reload
# or: poetry run python -m portal

# Tests
poetry run pytest
poetry run pytest tests/application/rbac/test_permission_service.py -v
```

| URL | Description |
|-----|-------------|
| `http://127.0.0.1:8000/healthz` | Public health check |
| `http://127.0.0.1:8000/admin/api/v1/...` | Admin API (authenticated) |
| `http://127.0.0.1:8000/api/v1/...` | App/public API surface |
| `http://127.0.0.1:8000/docs` | OpenAPI (basic auth on `/`) |

Copy `example.env` → `.env` before running locally.

---

## 3. Architecture (Clean Architecture)

**Rule of thumb:** dependencies point **inward**. Delivery and infrastructure depend on application and domain — never the reverse.

```
HTTP Request
  → Middleware (auth, session, locale)
  → Router (delivery)
  → Mapper: Serializer → Command
  → Service (application)
  → Port (domain Protocol)
  → Repository / Cache (infrastructure)
  → PostgreSQL / Redis
  → Result → Mapper → Serializer → JSON (camelCase)
```

### Layer map

| Layer | Path | Owns |
|-------|------|------|
| **Domain** | `portal/domain/` | `entities.py`, `ports.py` (Protocol), `constants.py`, audit table names |
| **Application** | `portal/application/` | `*_service.py`, `commands.py`, `results.py`, `mappers.py` (boundary only) |
| **Infrastructure** | `portal/infrastructure/` | `persistence/repositories/`, `cache/`, `events/` |
| **Delivery** | `portal/routers/`, `portal/serializers/`, `portal/middlewares/` | HTTP, API contracts |
| **ORM** | `portal/models/` | SQLAlchemy models only (not imported by services) |
| **DI** | `portal/containers/`, `portal/container.py` | Composition root |
| **Cross-cutting** | `portal/libs/`, `portal/providers/`, `portal/events/` | DB session, JWT, tracing, permission checker |
| **CLI** | `portal/cli/` | Thin Click entrypoints; seed logic in `application/cli/` |

### Hard dependency rules

1. `routers` → `application` (services) → `domain`
2. Application **must not** import `portal.serializers` (exception: `application/*/mappers.py`)
3. Application **must not** import `portal.models`
4. Repositories map to **domain entities** or **application results** — never `Admin*Serializer`
5. Infrastructure satisfies domain **Ports** via structural typing (no required inheritance)

---

## 4. Application Entry & HTTP Layout

### ASGI mount structure (`portal/apps.py`)

```
FastAPI (public)  portal.main:app
├── GET /healthz
├── mount /admin  →  Admin FastAPI app
│   └── /api/v1/...   (AuthMiddleware + RBAC)
└── mount /api    →  App FastAPI app
    └── /v1/...       (session + CORS; end-user auth TBD)
```

- **Admin API prefix:** `/admin/api/v1`
- **App API prefix:** `/api/v1`
- Admin routes use `AuthRouter` with JWT + permission metadata on each endpoint.
- `CoreRequestMiddleware` binds per-request DB session and resolved locale.

### Admin route modules (`portal/routers/admin/v1/`)

| Prefix | Module | Bounded context |
|--------|--------|-----------------|
| `/auth` | `auth.py` | Login, refresh, Microsoft |
| `/user` | `user.py` | Admin users |
| `/locale` | `locale.py` | System locales |
| `/verb` | `verb.py` | RBAC verbs |
| `/permission` | `permission.py` | Permissions |
| `/role` | `role.py` | Roles |
| `/resource` | `resource.py` | Menu/resources tree |
| `/facility/*` | `facility/` | Rooms, bookings, rentals, members |
| `/ministry/*` | `ministry/` | Ministry admin |
| `/org/*` | `org/` | Positions, member persons |

### App API (`portal/routers/apis/v1/`)

| Prefix | Notes |
|--------|-------|
| `/org` | Org-facing endpoints |
| `/ministry` | Ministry-facing endpoints |

---

## 5. Bounded Contexts & Services

### Core / platform

| Context | Application path | Key services |
|---------|------------------|--------------|
| **auth** | `application/auth/` | `LoginService`, `RefreshTokenService`, `MicrosoftAuthService`, `AdminUserService`, `UserReadService` |
| **rbac** | `application/rbac/` | `VerbService`, `PermissionService`, `RoleService`, `ResourceService` |
| **locale** | `application/locale/` | `LocaleService` |
| **audit** | `application/audit/` | `RbacAuditService` (emits operation events) |
| **cli** | `application/cli/` | `*_seed_service.py` (RBAC, locale, superuser, position seeds) |

### Business domains

| Context | Application path | Key services |
|---------|------------------|--------------|
| **facility** | `application/facility/` | `RoomService`, `RoomSlotTemplateService`, `RentalRateService`, `RentalCatalogService`, `PricingService`, `BookingService`, `MemberService`, `OverrideLogService` |
| **org** | `application/org/` | `MinistryService`, `MinistryApprovalService`, `PositionService`, `MemberPersonService` |

### Domain packages (`portal/domain/`)

| Package | Contents |
|---------|----------|
| `auth/` | `entities.py`, `ports.py` |
| `rbac/` | `entities.py`, `ports.py` |
| `locale/` | `entities.py`, `ports.py` |
| `facility/` | `constants.py`, `days_of_week_mask.py` |
| `org/`, `member/` | `constants.py` |
| `audit/` | Table name constants for audit events |
| `common/` | Shared mixins |

### ORM schemas (`portal/models/`)

PostgreSQL schemas are derived from model module paths (e.g. `auth`, `facility`, `org`, `member`, `audit`).

| Schema folder | Examples |
|---------------|----------|
| `auth/` | `user.py`, `rbac.py` |
| `facility/` | `room.py`, `booking.py`, `rental.py`, `room_slot_template.py` |
| `org/` | `ministry.py`, `position.py` |
| `member/` | `person.py` |
| `audit/` | `log.py` |
| `system_locale.py` | Locales |

Use mixins from `portal/models/mixins/` (`AuditMixin`, `DeletedMixin`, `SortableMixin`, `DescriptionMixin`, `RemarkMixin`). Parent/translation pattern: stable fields on parent; user-facing text on `*Translation` child tables.

---

## 6. Dependency Injection

**Composition root:** `portal/container.py` → `RootContainer`

```
RootContainer
├── core          (CoreContainer)     — DB, Redis, JWT, password, OIDC, blacklist
├── admin         (AdminContainer)    — auth, rbac, locale + nested:
│   ├── facility  (FacilityContainer)
│   └── org       (OrgContainer)
└── events        (EventsContainer)   — EventBus, admin operation log handler
```

- Routers inject services via `@inject` + `Depends(Provide[Container.<service>])`.
- Repositories receive `core.request_session` (request-scoped SQLAlchemy session).
- Caches receive `core.redis_client`.
- After adding a service, register it in the appropriate container and expose on `RootContainer` if routers need it.

**Reference:** `portal/containers/admin.py`, `facility.py`, `org.py`, `core.py`, `events.py`.

---

## 7. Request / Response Conventions

### Pydantic field naming

| Layer | Field style | `serialization_alias` |
|-------|-------------|----------------------|
| Commands / Results / Domain | `snake_case` | No |
| Request serializers (body, query) | `snake_case` | No |
| Response serializers (API output) | `snake_case` internally | **Yes** — `camelCase` for JSON |

Frontend sends snake_case query/body; API responses use camelCase.

### Mappers (`application/*/mappers.py`)

The **only** application files allowed to import `portal.serializers`.

```text
to_command(serializer)  → Command
to_api(result)        → Response serializer
```

Routers call mappers; services never see serializers.

### Multilingual content

- Translation rows keyed by `locale_id`.
- Shared query helpers: `infrastructure/persistence/repositories/shared/translation_queries.py`.
- Admin serializers often include translation tabs; see `serializers/admin/v1/org/translation.py` pattern.

### Pagination / sorting

- Common query base: `application/common/query_models.py`
- Repository pattern: `.where(condition, lambda: expr)` for optional filters
- Use `.fetchpages(..., as_model=SomeResult)` for paginated reads

---

## 8. Auth & Authorization

### Authentication flow (admin)

1. `AuthMiddleware` reads route `AuthConfig` from `AuthRouter` metadata.
2. Validates Bearer JWT via `JWTProvider` + `UserReadService`.
3. Sets `UserContext` for the request.
4. Checks permissions via `PermissionChecker` against route-declared `Permission.*` scopes.

### Login options

| Method | Endpoint | Notes |
|--------|----------|-------|
| Email/password | `POST /admin/api/v1/auth/login` | Returns access + refresh tokens |
| Token refresh | `POST /admin/api/v1/auth/refresh` | |
| Microsoft Entra | `POST /admin/api/v1/auth/microsoft` | SPA sends Entra ID token; user must pre-exist as admin |

### Permission constants

`portal/libs/consts/permission.py` — use `Permission.<RESOURCE>.<verb>` in router decorators.

---

## 9. Infrastructure Patterns

### Repositories (`infrastructure/persistence/repositories/`)

- Constructor: `__init__(self, session: Session)`
- Reads: `fetchrow` / `fetch` / `fetchpages` / `fetchval` with `as_model=ApplicationResult`
- Writes: `insert` / `update` / `delete` with plain `dict` payloads from services
- Filter soft-deleted: `is_deleted == False` unless listing deleted records

### Caches (`infrastructure/cache/`)

Used for locale list, permission detail, role detail, verb list. Invalidate on writes in services.

### Events (`portal/events/`, `infrastructure/events/`)

- `EventBus` publishes domain/admin events.
- `AdminOperationLogEventHandler` persists audit logs.
- RBAC mutating services call `RbacAuditService`.

### Tracing

Public service methods should use `@distributed_trace()` from `portal.libs.tracing.distributed_trace`.

### Database session

- Custom async session: `portal/libs/database/`
- `ModelBase` in `portal/libs/database/orm.py` auto-derives schema and `__tablename__`
- On HTTP/API exceptions, session is rolled back in `portal/apps.py` handlers

---

## 10. Testing

```
tests/
├── conftest.py              # Container fixture
├── application/
│   ├── auth/
│   ├── rbac/
│   ├── locale/
│   ├── facility/
│   └── org/
├── domain/
├── fixtures/                # Stub repositories, factories
└── test_*.py                # Integration-style tests
```

### Conventions

- `pytest` + `pytest-asyncio` + `pytest-mock`
- Async tests: `@pytest.mark.asyncio`
- **Application service tests:** inject stub repos implementing the same methods as Ports; assert on `results` types, not serializers
- Mirror `portal/application/` under `tests/application/`
- Run via Poetry: `poetry run pytest`

**Example stub pattern:** see `tests/application/rbac/test_permission_service.py`.

---

## 11. Adding a Feature (Vertical Slice Checklist)

Use **Permission** or **Verb** as the reference implementation.

1. **Domain** — `portal/domain/<ctx>/`
   - Add entities to `entities.py`
   - Add repository/cache ports to `ports.py` (Protocol)
   - Add audit table constants if needed (`domain/audit/constants.py`)

2. **Application** — `portal/application/<ctx>/`
   - `commands.py` — input models (snake_case)
   - `results.py` — output models
   - `<feature>_service.py` — use case logic; depend on Ports only
   - `mappers.py` — serializer ↔ command/result

3. **Infrastructure**
   - `infrastructure/persistence/repositories/<ctx>/<feature>_repository.py`
   - Optional: `infrastructure/cache/<feature>_cache.py`

4. **ORM** (if new tables)
   - `portal/models/<schema>/<entity>.py`
   - Register in `portal/models/__init__.py`
   - **Do not** edit `alembic/` — human runs migrations

5. **Delivery**
   - `serializers/admin/v1/<ctx>/` — request/response models
   - `routers/admin/v1/<ctx>/` — routes with `AuthRouter`, permissions, `@inject`
   - Register router in `routers/admin/v1/__init__.py`

6. **DI**
   - Register repo + service in `containers/admin.py` or nested container (`facility.py`, `org.py`)
   - Expose on `RootContainer` if needed

7. **Tests**
   - `tests/application/<ctx>/test_<feature>_service.py` with stubs

8. **Seed / CLI** (if needed)
   - Logic: `application/cli/<feature>_seed_service.py`
   - Entry: `portal/cli/<command>.py`

---

## 12. Naming Conventions

| Kind | Convention | Example |
|------|------------|---------|
| Variables, functions, files | `snake_case` | `permission_service.py` |
| Classes | `PascalCase` | `PermissionService` |
| Constants, env vars | `UPPER_SNAKE_CASE` | `JWT_SECRET_KEY` |
| ORM class | `{Schema}{Entity}` | `FacilityRoom`, `AuthRole` |
| Service file | `<entity>_service.py` | `room_service.py` |
| Comments | English only | |
| Imports | Top of file only | No imports inside functions |

---

## 13. Do NOT (Agent Guardrails)

| Action | Reason |
|--------|--------|
| Add/modify/delete `alembic/**` | Project policy — migrations are human-managed |
| Import `portal.models` in application services | Clean Architecture boundary |
| Import `portal.serializers` outside `mappers.py` | Boundary violation |
| Map repositories to `Admin*Serializer` | Use application `results` |
| Use non-ASCII in comments | Project standard |
| Run `git commit/push/merge` unless user asks | Automation policy |
| Check/format with black, isort, flake8 | Not used in this project |

---

## 14. Key Files Index

| File | Why read it |
|------|-------------|
| `README.md` | Architecture diagrams, setup, Alembic usage |
| `.cursor/rules/standard.mdc` | Full coding standards (ORM examples, repository patterns) |
| `portal/apps.py` | App mounting, middleware, exception handlers |
| `portal/container.py` | All wired services |
| `portal/routers/admin/v1/permission.py` | Canonical router pattern |
| `portal/application/rbac/permission_service.py` | Canonical service pattern |
| `portal/application/rbac/mappers.py` | Canonical mapper pattern |
| `portal/infrastructure/persistence/repositories/permission_repository.py` | Canonical repository pattern |
| `portal/middlewares/auth_middleware.py` | AuthZ flow |
| `portal/libs/consts/permission.py` | Permission tokens for routes |
| `portal/config.py` | Environment settings |
| `example.env` | Required env vars |

---

## 15. Mental Model for AI Agents

When given a task, first classify it:

| Task type | Start here |
|-----------|------------|
| New admin CRUD endpoint | Find similar router → trace to service → repo → model |
| Bug in business logic | `application/<ctx>/*_service.py` + tests in `tests/application/` |
| API contract / JSON shape | `serializers/admin/v1/` + `mappers.py` |
| DB query wrong | `infrastructure/persistence/repositories/` (not service) |
| Auth / 403 | `auth_middleware.py`, `permission_checker.py`, route `permissions=` |
| Cache stale | `infrastructure/cache/` + invalidation in service write paths |
| New table | `portal/models/` + human migration; then repository |
| Seed data | `application/cli/*_seed_service.py`, `portal/cli/` |

**Prefer minimal diffs.** Match existing patterns in the same bounded context before introducing new abstractions.
