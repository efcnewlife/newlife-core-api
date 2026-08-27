# Legal Document Effective Date and shared Markdown surfaces

Legal Documents (ADR 0010) are living Markdown, but Operators and visitors still need a clear **in-force** calendar day that is not the row's audit timestamp. We add a required **Effective Date** (`date`): Operators set it on create/update; saving body alone does not auto-bump it. **Last Updated** remains audit `updated_at`. Public GET includes Effective Date; Facility Booking shows it under the page title when content exists.

Authoring and reading use `@efcnewlife/newlife-ui` **MarkdownEditor** / **MarkdownPreview** with the built-in **`legal`** Markdown profile (Markdown string in/out). Portal edit uses MarkdownEditor (uncontrolled mode, default Edit; i18n chrome labels; TipTap peers installed). Portal Context menu View is a read-only Modal with metadata plus locale Tabs of MarkdownPreview (including soft-deleted rows). Facility Booking public pages use MarkdownPreview only and drop host-local `react-markdown` / custom link sanitizers so render rules stay aligned with the library.

## Considered Options

- **Use Last Updated (`updated_at`) as the public in-force date** — rejected: typo fixes would look like policy changes; legal "effective as of" is Operator-intent, not save time.
- **Auto-set Effective Date to today on every body save** — rejected: same false signal on minor edits; Effective Date must be explicit.
- **Effective from / Effective to range** — rejected: reopens expiry and public-read-after-end behavior; v1 needs one in-force day on the living document.
- **Optional Effective Date** — rejected: public pages would need empty/TBD behavior; required keeps the contract simple.
- **Host-local Markdown renderers (TextArea + `react-markdown`)** — rejected: diverges from library `legal` profile and sanitization; Editor/Preview pair already exists for this product.

## Consequences

- Parent Legal Document gains required `effective_date` (calendar day); human Alembic backfills existing seeded rows.
- Admin create/edit require Effective Date; list and View show Effective Date and Last Updated as separate fields.
- Public payload and Booking ToS/Privacy pages expose Effective Date; empty/not-found states omit that line.
- Portal and Facility Booking bump to `newlife-ui` ^0.6.0; only Portal installs TipTap peers.
