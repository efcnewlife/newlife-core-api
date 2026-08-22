# Deleting a Content File clears File associations after a named warning

Operators may delete a Content File that is still in a Room gallery (or other File associations). We do **not** block delete until unbind. Confirming delete removes the Content File **and every File association** for that file so no orphan rows remain.

The warning payload lists bound resources by name or code, **including soft-deleted Rooms**, marked as deleted. Soft-delete of a Room keeps associations so restore restores the gallery; hiding those Rooms would make delete look unused while restore would lose images.

## Considered Options

- **Reject delete while any association exists** — rejected: forces a separate unbind on every Room first.
- **Delete the file and leave association rows** — rejected: broken gallery reads and restore surprises.
- **Warn with counts only, or omit soft-deleted Rooms** — rejected: operators cannot tell what they are breaking.

## Consequences

- Bulk delete uses one confirmation over the selected files, then one cascade of files + associations.
- Admin clients must render the named list (including deleted Rooms), not only a count.
- Member-facing gallery is out of scope for this decision.
