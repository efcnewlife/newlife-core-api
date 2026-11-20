"""
CLI wiring: seed-room-slot-templates is a standalone command and an init-all step.
"""

import inspect

from portal.cli.init_all import init_all_process
from portal.cli.main import cli


def test_seed_room_slot_templates_command_is_registered():
    assert "seed-room-slot-templates" in cli.commands


def test_init_all_wires_the_room_slot_template_seed():
    source = inspect.getsource(init_all_process)
    assert "seed_room_slot_templates=seed_room_slot_templates_async" in source
