# Admin high-frequency failures carry stable error codes

Portal Operation feedback never shows raw English `detail`. Clients need stable `error_code` values (ADR 0001 pattern) beyond booking Scheduling Conflict and Room Blackout. This extends that contract to high-frequency admin not-found, uniqueness conflicts, and ministry steward/approval rule failures.

Enums live per domain (`FacilityErrorCode`, `OrgErrorCode`, `MemberErrorCode`, `AuthErrorCode`, `SystemErrorCode`). Application services raise `ApiBaseException` subclasses with `error_code=` (and optional `context`). Admin routers that previously used bare `HTTPException(404)` for get-by-id now raise `NotFoundException` with the matching code. `detail` stays English for logs; localization is a client concern.

## Considered Options

- **Localize `detail` via Accept-Language** — rejected for this change; Portal maps codes to i18n.
- **Code every 500 / every validation 422** — rejected; out of scope.
- **Parse `detail` on the client** — already rejected in ADR 0001.

## Consequences

- Booking codes `FACILITY_BOOKING_SCHEDULING_CONFLICT` and `FACILITY_BOOKING_ROOM_BLACKOUT` are unchanged.
- New codes include (non-exhaustive): `FACILITY_ROOM_NOT_FOUND`, `FACILITY_ROOM_CODE_EXISTS`, `FACILITY_BOOKING_NOT_FOUND`, `ORG_MINISTRY_NOT_FOUND`, `ORG_MINISTRY_PRIMARY_REQUIRED`, `ORG_MINISTRY_SECONDARY_REQUIRED`, `AUTH_ROLE_CODE_EXISTS`, `SYSTEM_SETTING_NOT_FOUND`, and related facility/org/member/auth/system tokens defined on the enums.
- Companion Portal issue maps these codes under `common:feedback.errors.*`.
