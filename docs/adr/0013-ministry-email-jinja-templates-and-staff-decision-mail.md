# Ministry application email templates (Jinja2) and staff decision notifications

ADR 0012 established Graph `Mail.Send`, bilingual EN-then-ZH bodies, and incumbent-only member approval. Ministry application emails still render as inline Python f-strings with minimal HTML. We replace that with **version-controlled Jinja2 templates** under `portal/templates/email/`, a reusable **`EmailTemplateRenderPort`** (application depends on the port; `TemplateRenderProvider` implements Jinja2 async), and Facility Booking **inline CSS** branding (Figma tokens: `#1e283f`, `#1865d8`, `#fab148`, `#e9f3f5`; text header in v1, no logo URL). Bilingual stacking and Graph transport are unchanged.

**Admin portal decisions** now send mail: an **Application decision email** to the applicant (`decision_channel=staff`) naming the staff member and stating they acted **on the Owner-position incumbent's behalf**; and an **Incumbent staff-decision notification email** to the current Owner incumbent (outcome summary, no further action). **Incumbent member decisions** keep the incumbent-channel decision email only. **`decision_channel`** is passed on approve/reject commands; `MinistryApprovalService` triggers mail inside approve/reject when a channel is set (member wrapper passes `incumbent`, admin router passes `staff`).

**Application summary** (ministry type, applicant, submitted_at in `America/Toronto`, target audiences, primary steward) appears only on the **Application notification email** (incumbent pending), not on submit confirmation or decision emails.

## Considered Options

- **Keep f-string builders** — rejected: hard to design review, no shared layout, blocks reuse for future mail types.
- **DB-editable templates (admin CMS)** — rejected for v1: deploy-reviewed files are enough; avoids schema and RBAC for template editing.
- **SMTP + Jinja like conf-portal-api** — rejected: this repo already committed to Graph in ADR 0012; only the render pattern is borrowed.
- **Single-language by recipient locale** — rejected: church policy remains bilingual stacking (ADR 0012).
- **Staff decision email without incumbent follow-up** — rejected: product wants the Owner incumbent informed when staff decide on their behalf (Q17).
- **Staff decision copy without naming the staff member** — rejected: audit stays on `approved_by_id` / `rejected_by_id`, but the body names the staff member while framing the act as on the incumbent's behalf.

## Consequences

- Add `jinja2` dependency; new `portal/templates/email/` tree (`base.html`, partials, four ministry templates including `incumbent_staff_decision_notification.html`).
- `MinistryApplicationMailService` builds template context (summary, bilingual names, links) and renders via port; retire f-string HTML in `ministry_application_mail_content.py` (subjects and context helpers may remain or move adjacent).
- Extend `ApproveMinistryCommand` / `RejectMinistryCommand` with optional `decision_channel`; admin ministry approve/reject routes pass `staff`.
- Tests: render snapshots or keyword assertions on HTML; mail service fakes assert applicant + incumbent sends on admin decision.
- `CONTEXT.md` glossary updated: Application decision email, Application summary (email), Incumbent staff-decision notification email.
- Out of scope for this ADR: plaintext multipart, mail queue/retry, per-recipient locale, hosted logo config, template preview API.
