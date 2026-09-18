"""
CLI wiring: seed-mock-data completes the near-term Mock fixture suite (#194).
"""

import inspect

from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error
from portal.cli.main import cli
from portal.cli.seed_mock_data import COMMAND_NAME, seed_mock_data_process


def test_seed_mock_data_command_is_registered():
    assert "seed-mock-data" in cli.commands
    assert COMMAND_NAME == "seed-mock-data"


def test_seed_mock_data_keeps_the_mock_lifecycle_environment_guard():
    source = inspect.getsource(seed_mock_data_process)
    assert "mock_lifecycle_environment_guard_error" in source
    assert "COMMAND_NAME" in source

    production = mock_lifecycle_environment_guard_error(is_prod=True, is_dev=False, force=True, command_name=COMMAND_NAME)
    staging_without_force = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=False, force=False, command_name=COMMAND_NAME)
    staging_with_force = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=False, force=True, command_name=COMMAND_NAME)
    dev = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=True, force=False, command_name=COMMAND_NAME)

    assert production is not None and COMMAND_NAME in production and "--force" not in production
    assert staging_without_force is not None and COMMAND_NAME in staging_without_force
    assert staging_with_force is None
    assert dev is None
