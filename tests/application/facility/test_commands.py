"""
Facility command validator tests.
"""
import pytest
from pydantic import ValidationError

from portal.application.facility.commands import CreateMinistryCommand, CreateRoomCommand
from tests.fixtures.facility.factories import make_translation


def test_create_room_command_requires_translations():
    with pytest.raises(ValidationError):
        CreateRoomCommand(code="room-a")


def test_create_room_command_rejects_name_only():
    with pytest.raises(ValidationError):
        CreateRoomCommand(code="room-a", name="Room A")


def test_create_room_command_accepts_translations():
    command = CreateRoomCommand(code="room-a", translations=[make_translation()])
    assert len(command.translations) == 1


def test_create_ministry_command_requires_translations():
    with pytest.raises(ValidationError):
        CreateMinistryCommand()


def test_create_ministry_command_rejects_name_only():
    with pytest.raises(ValidationError):
        CreateMinistryCommand(name="Youth")
