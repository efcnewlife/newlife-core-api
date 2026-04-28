from portal.libs.database.execute_result import affected_rows


def test_affected_rows_int():
    assert affected_rows(0) == 0
    assert affected_rows(3) == 3


def test_affected_rows_asyncpg_status():
    assert affected_rows("UPDATE 0") == 0
    assert affected_rows("UPDATE 1") == 1
    assert affected_rows("DELETE 2") == 2


def test_affected_rows_none():
    assert affected_rows(None) == 0
