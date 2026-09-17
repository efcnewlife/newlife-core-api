"""
Random Mock user persona generation for `seed-mock-users`.

Every seed run mints a fresh random identity per persona; nothing here is
idempotent by design (ADR 0025: every seed creates a new random QA dataset).
"""

import secrets
from dataclasses import dataclass
from typing import Callable

RandomToken = Callable[[], str]

PERSONA_PERSONAL = "personal"
PERSONA_STEWARD = "steward"
PERSONA_OWNER = "owner"
PERSONA_INACTIVE = "inactive"

_PERSONA_ORDER = (PERSONA_PERSONAL, PERSONA_STEWARD, PERSONA_OWNER, PERSONA_INACTIVE)

_PERSONA_PURPOSE = {
    PERSONA_PERSONAL: "Personal Rental Booking QA scenario",
    PERSONA_STEWARD: "Ministry steward QA scenario (Church Activity Booking)",
    PERSONA_OWNER: "Ministry approval queue QA scenario (Owner-position)",
    PERSONA_INACTIVE: "Mock login rejection QA scenario (inactive testing account)",
}


def default_random_token() -> str:
    """Return a 4-character lowercase alphanumeric token."""
    return secrets.token_hex(2)


@dataclass(frozen=True)
class MockUserPersona:
    """One generated Mock user identity."""

    persona: str
    email: str
    first_name: str
    last_name: str
    is_active: bool
    purpose: str


def generate_mock_user_personas(*, email_suffix: str, random_token: RandomToken = default_random_token) -> list[MockUserPersona]:
    """Generate the fixed personal/steward/owner/inactive persona set with fresh random identities."""
    personas: list[MockUserPersona] = []
    for persona in _PERSONA_ORDER:
        token = random_token()
        personas.append(
            MockUserPersona(
                persona=persona,
                email=f"{persona}.{token}{email_suffix}",
                first_name=f"{persona.capitalize()}+{token}",
                last_name="Mock",
                is_active=persona != PERSONA_INACTIVE,
                purpose=_PERSONA_PURPOSE[persona],
            )
        )
    return personas


def generate_mock_ministry_code(*, random_token: RandomToken = default_random_token) -> str:
    """Return a fresh QA-only Ministry identifier (Ministry has no stable business code)."""
    return f"MOCK-{random_token().upper()}"
