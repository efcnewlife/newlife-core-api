"""
Hours-only applicability rule engine unit tests.
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from portal.domain.facility.rate_applicability import (
    RateSelectionContext,
    coerce_applicability_from_db,
    matches_applicability,
    parse_applicability,
)


def test_parse_hours_gte_and_lt():
    gte = parse_applicability({"all": [{"op": "hours_gte", "value": 5}]})
    lt = parse_applicability({"all": [{"op": "hours_lt", "value": 5}]})
    assert gte == {"all": [{"op": "hours_gte", "value": "5"}]}
    assert lt == {"all": [{"op": "hours_lt", "value": "5"}]}


def test_parse_hours_range():
    rule = parse_applicability(
        {"all": [{"op": "hours_range", "min": 0, "max": 5, "max_exclusive": True}]}
    )
    assert rule["all"][0]["op"] == "hours_range"
    assert rule["all"][0]["max_exclusive"] is True


def test_parse_rejects_unknown_op():
    with pytest.raises(ValidationError):
        parse_applicability({"op": "hours_gtte", "value": 5})


def test_parse_none_means_always_eligible():
    assert parse_applicability(None) is None


def test_matches_null_rule():
    ctx = RateSelectionContext(billed_hours=Decimal("3"))
    assert matches_applicability(None, ctx) is True


def test_matches_hours_gte_and_lt_pdf_switch():
    hourly = {"all": [{"op": "hours_lt", "value": 5}]}
    daily = {"all": [{"op": "hours_gte", "value": 5}]}
    below = RateSelectionContext(billed_hours=Decimal("4.99"))
    at = RateSelectionContext(billed_hours=Decimal("5"))
    assert matches_applicability(hourly, below) is True
    assert matches_applicability(daily, below) is False
    assert matches_applicability(hourly, at) is False
    assert matches_applicability(daily, at) is True


def test_matches_hours_range_exclusive():
    rule = {"all": [{"op": "hours_range", "min": 0, "max": 5, "max_exclusive": True}]}
    assert matches_applicability(rule, RateSelectionContext(Decimal("4.99"))) is True
    assert matches_applicability(rule, RateSelectionContext(Decimal("5"))) is False


def test_matches_any_and_not():
    rule = {
        "any": [
            {"op": "hours_lt", "value": 2},
            {"not": {"op": "hours_lt", "value": 8}},
        ]
    }
    assert matches_applicability(rule, RateSelectionContext(Decimal("1"))) is True
    assert matches_applicability(rule, RateSelectionContext(Decimal("9"))) is True
    assert matches_applicability(rule, RateSelectionContext(Decimal("5"))) is False


def test_invalid_stored_rule_does_not_match():
    assert matches_applicability({"op": "nope"}, RateSelectionContext(Decimal("1"))) is False


def test_coerce_applicability_from_db_json_string():
    raw = '{"all": [{"op": "hours_lt", "value": "5"}]}'
    assert coerce_applicability_from_db(raw) == {"all": [{"op": "hours_lt", "value": "5"}]}


def test_parse_applicability_accepts_json_string():
    raw = '{"all": [{"op": "hours_gte", "value": 5}]}'
    assert parse_applicability(raw) == {"all": [{"op": "hours_gte", "value": "5"}]}


def test_matches_applicability_accepts_json_string():
    raw = '{"all": [{"op": "hours_lt", "value": 5}]}'
    ctx = RateSelectionContext(billed_hours=Decimal("4"))
    assert matches_applicability(raw, ctx) is True
