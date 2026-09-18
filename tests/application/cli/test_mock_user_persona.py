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
    calls = iter(["aaaa", "bbbb", "cccc", "dddd", "eeee", "ffff", "gggg", "hhhh", "iiii", "jjjj"])
    return lambda: next(calls)


def test_generate_mock_user_personas_returns_the_agreed_persona_matrix():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    assert [p.persona for p in personas] == [
        PERSONA_PERSONAL,
        PERSONA_PERSONAL,
        PERSONA_PERSONAL,
        PERSONA_PERSONAL,
        PERSONA_PERSONAL,
        PERSONA_STEWARD,
        PERSONA_STEWARD,
        PERSONA_STEWARD,
        PERSONA_OWNER,
        PERSONA_INACTIVE,
    ]


def test_generate_mock_user_personas_email_and_name_format():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    assert [p.email for p in personas] == [
        "personal.aaaa@test.local",
        "personal.bbbb@test.local",
        "personal.cccc@test.local",
        "personal.dddd@test.local",
        "personal.eeee@test.local",
        "steward.ffff@test.local",
        "steward.gggg@test.local",
        "steward.hhhh@test.local",
        "owner.iiii@test.local",
        "inactive.jjjj@test.local",
    ]
    assert personas[0].first_name == "Personal+aaaa"
    assert personas[0].last_name == "Mock"


def test_generate_mock_user_personas_only_inactive_persona_is_inactive():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    assert [p.is_active for p in personas] == [True, True, True, True, True, True, True, True, True, False]


def test_generate_mock_user_personas_uses_configured_suffix():
    personas = generate_mock_user_personas(email_suffix="@qa.test", random_token=_fixed_token())

    assert all(p.email.endswith("@qa.test") for p in personas)


def test_generate_mock_user_personas_repeated_personas_have_distinct_purposes():
    personas = generate_mock_user_personas(email_suffix="@test.local", random_token=_fixed_token())

    purposes = [p.purpose for p in personas]
    assert len(purposes) == 10
    assert len(set(purposes)) == 10
    assert set(p.persona for p in personas) == {PERSONA_PERSONAL, PERSONA_STEWARD, PERSONA_OWNER, PERSONA_INACTIVE}


def test_generate_mock_ministry_code_is_prefixed_and_uppercase():
    code = generate_mock_ministry_code(random_token=lambda: "ab12")

    assert code == "MOCK-AB12"
