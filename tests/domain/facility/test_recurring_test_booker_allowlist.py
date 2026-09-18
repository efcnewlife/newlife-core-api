"""Recurring Booking test Booker allowlist matching helper."""

from portal.domain.facility.recurring import is_test_booker_allowlisted


def test_exact_email_address_matches():
    assert is_test_booker_allowlisted("qa1@test.local", ["qa1@test.local"], []) is True


def test_email_matching_is_case_and_whitespace_insensitive():
    assert is_test_booker_allowlisted("  QA1@Test.Local  ", ["qa1@test.local"], []) is True


def test_unlisted_exact_email_does_not_match():
    assert is_test_booker_allowlisted("qa2@test.local", ["qa1@test.local"], []) is False


def test_complete_domain_suffix_matches():
    assert is_test_booker_allowlisted("anyone@qa.test.local", [], ["@qa.test.local"]) is True


def test_domain_suffix_forbids_substring_match():
    assert is_test_booker_allowlisted("anyone@notqa.test.local", [], ["@qa.test.local"]) is False


def test_domain_suffix_requires_the_at_sign_boundary():
    # A bare "test.local" suffix (no leading "@") must never match; only pre-normalized "@test.local" values do.
    assert is_test_booker_allowlisted("anyone@evilxtest.local", [], ["@test.local"]) is False


def test_missing_email_never_matches():
    assert is_test_booker_allowlisted(None, ["qa1@test.local"], ["@test.local"]) is False


def test_empty_allowlist_never_matches():
    assert is_test_booker_allowlisted("qa1@test.local", [], []) is False
