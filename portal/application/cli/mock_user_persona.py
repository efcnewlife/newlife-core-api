"""
Random Mock user persona generation for `seed-mock-users`.

Every seed run mints a fresh random identity per roster slot; nothing here is
idempotent by design (ADR 0025: every seed creates a new random QA dataset).
Repeated personal and steward slots keep the existing persona vocabulary and
use distinct `purpose` values so inventory rows stay selectable.
"""

import secrets
from dataclasses import dataclass
from typing import Callable

RandomToken = Callable[[], str]

PERSONA_PERSONAL = "personal"
PERSONA_STEWARD = "steward"
PERSONA_OWNER = "owner"
PERSONA_INACTIVE = "inactive"

# (persona, purpose, is_active) - repeated personas keep the same label.
_PERSONA_SPECS = (
    (PERSONA_PERSONAL, "Personal Rental Booking QA scenario", True),
    (PERSONA_PERSONAL, "Personal Rental Booking display density (2)", True),
    (PERSONA_PERSONAL, "Personal Rental Booking display density (3)", True),
    (PERSONA_PERSONAL, "Personal Rental Booking display density (4)", True),
    (PERSONA_PERSONAL, "Personal Rental Booking display density (5)", True),
    (PERSONA_STEWARD, "Ministry steward QA scenario (Church Activity Booking)", True),
    (PERSONA_STEWARD, "Ministry secondary steward QA scenario", True),
    (PERSONA_STEWARD, "Ministry secondary steward display density", True),
    (PERSONA_OWNER, "Ministry approval queue QA scenario (Owner-position)", True),
    (PERSONA_INACTIVE, "Mock login rejection QA scenario (inactive testing account)", False),
)


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
    """Generate the agreed Testing-account roster with fresh random identities."""
    personas: list[MockUserPersona] = []
    for persona, purpose, is_active in _PERSONA_SPECS:
        token = random_token()
        personas.append(
            MockUserPersona(
                persona=persona,
                email=f"{persona}.{token}{email_suffix}",
                first_name=f"{persona.capitalize()}+{token}",
                last_name="Mock",
                is_active=is_active,
                purpose=purpose,
            )
        )
    return personas


def generate_mock_ministry_code(*, random_token: RandomToken = default_random_token) -> str:
    """Return a fresh QA-only Ministry identifier (Ministry has no stable business code)."""
    return f"MOCK-{random_token().upper()}"
