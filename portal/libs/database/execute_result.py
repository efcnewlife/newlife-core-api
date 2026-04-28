"""
Helpers for values returned from Session.execute (asyncpg status strings, etc.).
"""


def affected_rows(execute_result) -> int:
    """Return row count from a Session.execute() result (int or e.g. 'UPDATE 1')."""
    if execute_result is None:
        return 0
    if isinstance(execute_result, int):
        return execute_result
    text = str(execute_result).strip()
    parts = text.split()
    if not parts:
        return 0
    last = parts[-1]
    if last.isdigit():
        return int(last)
    return 0
