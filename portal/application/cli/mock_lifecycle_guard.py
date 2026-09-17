"""
Environment guard shared by Mock QA data lifecycle CLI commands.

Stricter than the generic `not IS_DEV and not force` gate used by catalog seed
commands: production is never allowed, even with --force.
"""

from typing import Optional


def mock_lifecycle_environment_guard_error(*, is_prod: bool, is_dev: bool, force: bool, command_name: str) -> Optional[str]:
    """Return a blocking error message, or None when the command may proceed."""
    if is_prod:
        return f"{command_name} is never allowed when ENV='prod'."
    if not is_dev and not force:
        return f"{command_name} is blocked outside dev. Pass --force to proceed in staging."
    return None
