"""
CLI wiring: remove-mock-data hard-deletes Mock QA data seeded by seed-mock-users / seed-mock-data.
"""

import inspect

from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error
from portal.cli.main import cli
from portal.cli.remove_mock_data import COMMAND_NAME, remove_mock_data_process


def test_remove_mock_data_command_is_registered():
    assert "remove-mock-data" in cli.commands
    assert COMMAND_NAME == "remove-mock-data"


def test_remove_mock_data_exposes_include_legacy_demo_flag():
    params = {param.name: param for param in cli.commands["remove-mock-data"].params}

    assert params["include_legacy_demo"].is_flag is True
    assert params["include_legacy_demo"].default is False
    assert params["force"].is_flag is True


def test_remove_mock_data_keeps_the_mock_lifecycle_environment_guard():
    source = inspect.getsource(remove_mock_data_process)
    assert "mock_lifecycle_environment_guard_error" in source
    assert "COMMAND_NAME" in source
    assert "include_legacy_demo" in source

    production = mock_lifecycle_environment_guard_error(is_prod=True, is_dev=False, force=True, command_name=COMMAND_NAME)
    staging_without_force = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=False, force=False, command_name=COMMAND_NAME)
    staging_with_force = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=False, force=True, command_name=COMMAND_NAME)
    dev = mock_lifecycle_environment_guard_error(is_prod=False, is_dev=True, force=False, command_name=COMMAND_NAME)

    assert production is not None and COMMAND_NAME in production and "--force" not in production
    assert staging_without_force is not None and COMMAND_NAME in staging_without_force
    assert staging_with_force is None
    assert dev is None
