"""
CLI wiring: seed-mock-data completes the QA scenarios seed-mock-users starts (#175).
"""

from portal.cli.main import cli


def test_seed_mock_data_command_is_registered():
    assert "seed-mock-data" in cli.commands
