"""
Heuristics to exclude shared mailboxes and service accounts from directory sync.
"""
import re
from typing import Optional

from portal.providers.ms_graph.models import GraphUserRecord

# Surnames commonly used on functional accounts (from tenant export review).
BLOCKED_SURNAME_TOKENS: frozenset[str] = frozenset(
    {
        "nl",
        "efcnl",
        "efc nl",
        "it",
        "creative team",
        "youth group",
        "school",
        "new life",
        "newlife",
        "efc new life",
        "efc newlife",
        "efcnewlife",
    }
)

# Functional mailbox local-parts (exact match, before @).
BLOCKED_EMAIL_LOCAL_EXACT: frozenset[str] = frozenset(
    {
        "worship",
        "finance.nl",
        "office_newlife",
        "betternewlife",
        "church",
        "tonychurch",
        "sermon",
        "elder",
        "bak1",
        "education",
        "newlife",
        "efcnl",
        "salt",
        "guanghua",
        "anniversary",
        "dev",
        "it",
        "caring",
    }
)

# Functional mailbox local-part prefixes.
BLOCKED_EMAIL_LOCAL_PREFIXES: tuple[str, ...] = (
    "uploader",
    "pictures",
    "video",
    "efcnl_",
    "office_",
    "website.",
    "chinese.",
    "english.",
    "signage.",
)

# Regex for numbered service accounts: uploader2_ct, video1, bak1, pictures1.
BLOCKED_EMAIL_LOCAL_PATTERN = re.compile(
    r"^(uploader\d|pictures\d|video\d|bak\d)",
    re.IGNORECASE,
)

# Display / preferred name hints on shared or test mailboxes.
BLOCKED_DISPLAY_KEYWORDS: tuple[str, ...] = (
    "service account",
    "test account",
    "church secretary",
    "yearbook",
)


def email_local_part(email: str) -> str:
    return email.strip().lower().split("@", 1)[0]


def classify_service_account(record: GraphUserRecord, email: str) -> Optional[str]:
    """
    Return a skip reason when the Graph user looks like a shared/service mailbox.
    """
    local_part = email_local_part(email)
    surname = (record.surname or "").strip().lower()
    display_name = (record.display_name or "").strip().lower()

    if local_part in BLOCKED_EMAIL_LOCAL_EXACT:
        return f"blocked_email_local:{local_part}"

    for prefix in BLOCKED_EMAIL_LOCAL_PREFIXES:
        if local_part.startswith(prefix):
            return f"blocked_email_prefix:{prefix}"

    if BLOCKED_EMAIL_LOCAL_PATTERN.match(local_part):
        return f"blocked_email_pattern:{local_part}"

    if surname in BLOCKED_SURNAME_TOKENS:
        return f"blocked_surname:{surname}"

    for keyword in BLOCKED_DISPLAY_KEYWORDS:
        if keyword in display_name:
            return f"blocked_display_name:{keyword}"

    return None


def is_syncable_person(record: GraphUserRecord, email: str) -> bool:
    """True when the record passes person and non-service heuristics."""
    given_name = (record.given_name or "").strip()
    surname = (record.surname or "").strip()
    if not given_name or not surname:
        return False
    return classify_service_account(record, email) is None
