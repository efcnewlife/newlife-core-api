from uuid import uuid4

import pytest
from pydantic import ValidationError

from portal.libs.consts.enums import ResourceType
from portal.serializers.admin.v1.facility.rental_rate import AdminRentalRateCreate
from portal.serializers.admin.v1.facility.room import AdminRoomCreate
from portal.serializers.admin.v1.ministry import AdminMinistryCreate
from portal.serializers.admin.v1.permission import AdminPermissionCreate, AdminPermissionUpdate
from portal.serializers.admin.v1.resource import AdminResourceCreate, AdminResourceUpdate
from portal.serializers.admin.v1.role import AdminRoleCreate, AdminRoleUpdate


def _translation(locale_id):
    return {
        "locale_id": str(locale_id),
        "name": "name",
        "description": "desc",
        "remark": "remark",
    }


def test_create_requires_translations():
    with pytest.raises(ValidationError):
        AdminPermissionCreate(
            code="permission_code",
            resource_id=uuid4(),
            verb_id=uuid4(),
            is_active=True,
        )

    with pytest.raises(ValidationError):
        AdminResourceCreate(
            key="resource_key",
            code="resource_code",
            icon="icon",
            path="/path",
            type=ResourceType.SYSTEM,
            is_visible=True,
        )

    with pytest.raises(ValidationError):
        AdminRoleCreate(
            code="role_code",
            is_active=True,
            permissions=[],
        )


def test_create_rejects_legacy_name_only():
    with pytest.raises(ValidationError):
        AdminPermissionCreate(
            code="permission_code",
            resource_id=uuid4(),
            verb_id=uuid4(),
            is_active=True,
            name="Legacy Name",
        )

    with pytest.raises(ValidationError):
        AdminRoomCreate(
            code="room-a",
            name="Room A",
        )

    with pytest.raises(ValidationError):
        AdminMinistryCreate(name="Youth")

    with pytest.raises(ValidationError):
        AdminRentalRateCreate(
            facility_id=uuid4(),
            unit_amount="10",
            name="Hourly",
        )


def test_update_allows_non_i18n_only_payload():
    permission = AdminPermissionUpdate(
        code="permission_code",
        resource_id=uuid4(),
        verb_id=uuid4(),
        is_active=True,
    )
    resource = AdminResourceUpdate(
        key="resource_key",
        code="resource_code",
        icon="icon",
        path="/path",
        type=ResourceType.SYSTEM,
        is_visible=True,
    )
    role = AdminRoleUpdate(
        code="role_code",
        is_active=True,
        permissions=[],
    )
    assert permission.translations is None
    assert resource.translations is None
    assert role.translations is None


def test_duplicate_locale_id_is_rejected():
    locale_id = uuid4()

    with pytest.raises(ValidationError):
        AdminPermissionCreate(
            code="permission_code",
            resource_id=uuid4(),
            verb_id=uuid4(),
            is_active=True,
            translations=[_translation(locale_id), _translation(locale_id)],
        )

    with pytest.raises(ValidationError):
        AdminResourceCreate(
            key="resource_key",
            code="resource_code",
            icon="icon",
            path="/path",
            type=ResourceType.SYSTEM,
            is_visible=True,
            translations=[_translation(locale_id), _translation(locale_id)],
        )

    with pytest.raises(ValidationError):
        AdminRoleCreate(
            code="role_code",
            is_active=True,
            permissions=[],
            translations=[_translation(locale_id), _translation(locale_id)],
        )


def test_create_accepts_multiple_translations():
    locale_1 = uuid4()
    locale_2 = uuid4()
    permission = AdminPermissionCreate(
        code="permission_code",
        resource_id=uuid4(),
        verb_id=uuid4(),
        is_active=True,
        translations=[_translation(locale_1), _translation(locale_2)],
    )
    assert permission.translations is not None
    assert len(permission.translations) == 2
