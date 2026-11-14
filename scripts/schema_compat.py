"""
Compare a database's Alembic revision with the migrations of the checked-out version (ADR 0039).

Pass the revision the operator read from the target database (select version_num from alembic_version; "none" for
an empty table) and a clean checkout of the version you plan to deploy or roll back to (default: this checkout).
Versions older than this script have no copy of it, so run it from a current checkout. Never connects to a database.

    uv run python scripts/schema_compat.py <revision|none> [checkout]

Exit codes:
    0  current  the database is at this version's head
    3  behind   this version has migrations the database lacks: run alembic upgrade head from this checkout
    4  ahead    the database has a revision this version does not know: it was migrated by a newer version.
                Deploy or roll back to this version only after confirming those newer migrations are additive.
    1  error    (for example, several heads); 2  usage
"""

import sys
from enum import Enum
from pathlib import Path

from alembic.script import ScriptDirectory
from alembic.util import CommandError

DEFAULT_CHECKOUT = Path(__file__).resolve().parents[1]


class SchemaCompatError(Exception):
    pass


class Decision(str, Enum):
    CURRENT = "current"
    BEHIND = "behind"
    AHEAD = "ahead"


EXIT_CODES = {Decision.CURRENT: 0, Decision.BEHIND: 3, Decision.AHEAD: 4}

MESSAGES = {
    Decision.CURRENT: "current: the database is at this version's head {head}",
    Decision.BEHIND: "behind: this version expects {head}; run alembic upgrade head from this checkout",
    Decision.AHEAD: (
        "ahead: {revision} is unknown to this version (head {head}); a newer version migrated the database. "
        "Confirm the newer migrations are additive before running this version."
    ),
}


def decide(script: ScriptDirectory, db_revision: str | None) -> Decision:
    heads = script.get_heads()
    if len(heads) != 1:
        raise SchemaCompatError(f"expected one Alembic head, found heads {sorted(heads)}")
    head = heads[0]
    if db_revision == head:
        return Decision.CURRENT
    if db_revision is None:
        return Decision.BEHIND
    try:
        script.get_revision(db_revision)
    except CommandError:
        return Decision.AHEAD
    return Decision.BEHIND


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print("Usage: schema_compat.py <revision|none> [checkout]", file=sys.stderr)
        return 2
    revision = None if argv[0] == "none" else argv[0]
    alembic_dir = Path(argv[1] if len(argv) == 2 else DEFAULT_CHECKOUT) / "alembic"
    if not alembic_dir.is_dir():
        print(f"error: {alembic_dir} not found", file=sys.stderr)
        return 1
    script = ScriptDirectory(str(alembic_dir))
    try:
        decision = decide(script, revision)
    except SchemaCompatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(MESSAGES[decision].format(head=script.get_current_head(), revision=revision))
    return EXIT_CODES[decision]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
