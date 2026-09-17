"""
Tests for random Mock user persona generation.
"""

from portal.application.cli.mock_user_persona import (
    PERSONA_INACTIVE,
    PERSONA_OWNER,
    PERSONA_PERSONAL,
    PERSONA_STEWARD,
    generate_mock_ministry_code,
    generate_mock_user_personas,
)


def _fixed_token():
    calls = iter(["aaaa", "bbbb", "cccc", "dddd", "eeee"])
    return lambda: next(calls)


def test_generate_mock_user_personas_returns_the_four_fixed_personas():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    assert [p.persona for p in personas] == [PERSONA_PERSONAL, PERSONA_STEWARD, PERSONA_OWNER, PERSONA_INACTIVE]


def test_generate_mock_user_personas_email_and_name_format():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    personal = personas[0]
    assert personal.email == "personal.aaaa@test.local"
    assert personal.first_name == "Personal+aaaa"
    assert personal.last_name == "Mock"


def test_generate_mock_user_personas_only_inactive_persona_is_inactive():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    active_flags = {p.persona: p.is_active for p in personas}
    assert active_flags[PERSONA_PERSONAL] is True
    assert active_flags[PERSONA_STEWARD] is True
    assert active_flags[PERSONA_OWNER] is True
    assert active_flags[PERSONA_INACTIVE] is False


def test_generate_mock_user_personas_uses_configured_suffix():
    personas = generate_mock_user_personas(email_suffix="@qa.test", random_token=_fixed_token())

    assert all(p.email.endswith("@qa.test") for p in personas)


def test_generate_mock_user_personas_each_persona_has_a_distinct_purpose():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    purposes = {p.purpose for p in personas}
    assert len(purposes) == 4


def test_generate_mock_ministry_code_is_prefixed_and_uppercase():
    code = generate_mock_ministry_code(random_token=lambda: "ab12")

    assert code == "MOCK-AB12"
