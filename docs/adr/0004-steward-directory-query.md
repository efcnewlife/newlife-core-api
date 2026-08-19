# Steward directory query is not ministry pages keyword

Admin operators need to find which Ministries a person stewards without opening each Ministry, but the Steward roster write model stays one Ministry at a time. We add a **Steward directory query**: the result is Ministries (not membership rows). A `q` may match Ministry name or a Steward's display name / email. The payload does **not** include the Steward roster; clients load the roster from existing Ministry detail.

We do **not** extend generic ministry `pages` `keyword` (translation name only). That list is Ministry CRUD search. Mixing steward identity into it would make the Ministries page silently find people.

## Considered Options

- **Embed steward summaries on every list/pages row** — rejected: larger payload and a second copy of the roster next to detail; the Portal landing only needs names in the rail after a click.
- **N+1 GET detail for client-side person search** — rejected: slow and brittle as Ministry count grows.
- **Reuse `keyword` on GET pages** — rejected: Ministry CRUD would start matching people.
- **Membership-row list API** — rejected: the domain write is still replace-one-roster; a person×Ministry table fights that grain.

## Consequences

- Directory and detail stay different reads. Tests of directory query must not assume `members` on the items.
- Portal (and any other admin client) must call the dedicated directory query, then GET detail for the selected Ministry.
- `GET .../ministries/list` stays the active-only picker; it is not the steward directory (it omits draft / pending / inactive / rejected).
