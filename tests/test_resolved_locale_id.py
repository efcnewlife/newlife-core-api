from uuid import UUID

import pytest

from portal.libs.contexts.request_context import (
    get_resolved_locale_id,
    get_request_context,
    reset_request_context,
    set_request_context,
    RequestContext,
)
from portal.schemas.base import HeaderInfo


def test_get_resolved_locale_id_no_context():
    with pytest.raises(LookupError):
        get_request_context()
    assert get_resolved_locale_id() is None


def test_get_resolved_locale_id_set():
    loc = UUID("12345678-1234-5678-1234-567812345678")
    ctx = RequestContext(headers=HeaderInfo(), resolved_locale_id=loc)
    token = set_request_context(ctx)
    try:
        assert get_resolved_locale_id() == loc
    finally:
        reset_request_context(token)
