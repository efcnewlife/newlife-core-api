# File association resource kind is a stable token, not a class name

Room gallery binds Content Files through `ContentFileAssociation`. Conf-portal stored the **handler class name** as `resource_name`, which breaks when the class is renamed. We store a **stable resource kind**. For a Room gallery that token is `facility.room` (same grain as RBAC resource keys).

## Considered Options

- **Handler / service class name** — rejected: identity would track code layout, not the Room.
- **ORM class or table name** — rejected: schema or model renames would orphan existing associations.
- **Stable token `facility.room`** — accepted.

## Consequences

- Association writes and reads for Room gallery filter on `resource_name = "facility.room"` plus the Room id.
- Other resources that later bind Content Files get their own tokens; they must not reuse `facility.room`.
