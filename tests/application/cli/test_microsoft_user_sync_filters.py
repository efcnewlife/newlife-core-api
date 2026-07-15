"""
Tests for Microsoft user sync service-account heuristics.
"""
import pytest

from portal.application.cli.microsoft_user_sync_filters import (
    classify_service_account,
    is_syncable_person,
)
from portal.providers.microsoft_graph_provider import GraphUserRecord


def _record(
    *,
    email: str,
    given_name: str,
    surname: str,
    display_name: str | None = None,
) -> GraphUserRecord:
    return GraphUserRecord(
        object_id=email.split("@", 1)[0],
        email=email,
        given_name=given_name,
        surname=surname,
        display_name=display_name or f"{given_name} {surname}",
        account_enabled=True,
        user_principal_name=email,
        user_type="Member",
    )


@pytest.mark.parametrize(
    "email,given_name,surname,display_name",
    [
        ("dev@efcnewlife.org", "DEV", "EFCNL", "DEV EFCNL"),
        ("worship@efcnewlife.org", "Worship", "New Life", "Worship New Life"),
        ("uploader3@efcnewlife.org", "Uploader 3", "Creative Team", "Uploader 3 Creative Team"),
        ("pictures1@efcnewlife.org", "Pictures1", "EFCNL", "Pictures1 EFCNL (service account)"),
        ("it@efcnewlife.org", "Tony", "Ho", "Tony Ho"),
        ("chinese.fellowship@efcnewlife.org", "Chinese Fellowship", "EFCNL", "Chinese Fellowship EFCNL"),
    ],
)
def test_classify_service_account_detects_functional_mailboxes(
    email: str,
    given_name: str,
    surname: str,
    display_name: str,
):
    record = _record(
        email=email,
        given_name=given_name,
        surname=surname,
        display_name=display_name,
    )
    assert classify_service_account(record, email) is not None


@pytest.mark.parametrize(
    "email,given_name,surname",
    [
        ("jay.hsia@efcnewlife.org", "Jay", "Hsia"),
        ("eugene.chen@efcnewlife.org", "Eugene", "Chen"),
        ("gvoden@efcnewlife.org", "George", "Vodenitcharov"),
        ("jonq@efcnewlife.org", "Jon", "Qiu"),
        ("faith.hsieh@efcnewlife.org", "Faith", "Hsieh"),
    ],
)
def test_classify_service_account_allows_real_people(email: str, given_name: str, surname: str):
    record = _record(email=email, given_name=given_name, surname=surname)
    assert classify_service_account(record, email) is None
    assert is_syncable_person(record, email) is True


def test_tony_hoho_test_account_blocked_by_display_name():
    record = GraphUserRecord(
        object_id="test",
        email="tony.hoho@efcnewlife.org",
        given_name="Tony",
        surname="HoHo",
        display_name="Tony Ho (test account)",
        user_principal_name="tony.hoho@efcnewlife.org",
    )
    assert classify_service_account(record, "tony.hoho@efcnewlife.org") is not None
