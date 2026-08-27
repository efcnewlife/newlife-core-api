# Legal Document is Product × Kind, living Markdown, public-read

Facility Booking (and later Portal) need Operator-editable Terms of Service and Privacy Policy. We model each as a **Legal Document**: one living Markdown body per **Product** code × **Legal Document Kind**, with locale translations. Identity is the built-in pair (`facility-booking` | `portal` × `terms_of_service` | `privacy_policy`), not a free title. Public consumers read the current active row without auth (Product + Kind; Accept-Language + default-locale fallback). Empty active body is still the document (200 + empty); soft-deleted or missing is not found. We do **not** version the text or record acceptance in this design.

Admin follows normal RBAC and DataPage soft-delete / restore. Delete is not blocked because a row was seeded; Operators confirm the public-read risk and may restore. Create may only pick from the built-in Product × Kind catalog, and only when **no** row exists for that pair (including none soft-deleted). If a soft-deleted twin exists, create is rejected and the Operator restores instead.

## Considered Options

- **Stuff the body into System Setting JSON** — rejected: wrong tool for localized long-form Markdown and public legal pages; Setting also blocks built-in delete.
- **One church-wide ToS blob (no Product)** — rejected: Facility Booking and Portal need separate texts; Product is the seam for more apps later.
- **Legal Document Kind omitted; ToS-only table** — rejected: Privacy Policy is already required; Kind avoids a second parallel feature.
- **Versioned documents + acceptance log** — rejected: v1 only displays current text; versioning and consent are hard to reverse and out of scope.
- **Forbid soft-delete on seeded rows** — rejected: special-casing built-in delete adds complexity; risk belongs in Operator confirmation under RBAC.
- **Create while a soft-deleted twin exists (or free-text Product codes)** — rejected: duplicates and CMS drift; catalog + restore-or-create-when-absent keeps one row per pair.

## Consequences

- Seed four rows for this slice (`facility-booking` and `portal` × both kinds); bodies may start empty.
- One unauthenticated public GET parameterized by Product and Kind; member apps hard-code their Product (Facility Booking uses `facility-booking`).
- Portal Content owns the Legal Documents list; Portal Login / public legal pages for `portal` are out of this slice.
- Facility Booking exposes `/terms-of-service` and `/privacy-policy` plus Footer and Login links; titles come from client i18n by Kind, not an editable title field.
- Body storage is Markdown only (no HTML, no images) so public render stays a fixed, limited surface.
- Effective Date vs Last Updated, and host MarkdownEditor / MarkdownPreview (`legal` profile), are decided in ADR 0011.

## Human migration note (agents do not edit `alembic/versions/`)

ORM models live under `portal/models/content/legal_document.py`. A human should generate and apply an Alembic revision that creates:

| Schema    | Table                        | Notes                                                                                                                                                                     |
| --------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `content` | `legal_document`             | Columns: `product` (varchar 64), `kind` (varchar 64), audit + soft-delete mixins; unique `(product, kind)`; index on `(product, kind, is_deleted)`                        |
| `content` | `legal_document_translation` | Columns: `legal_document_id` (FK cascade), `locale_id` (FK to `system_locale`), `body` (text, default empty string), audit mixin; unique `(legal_document_id, locale_id)` |

After migrate: `uv run python -m portal.cli.main seed-legal-documents` (and re-run `init-rbac` / `reset-rbac` so `content:legal_document` permissions and menu exist).
