"""Super Admin staff/user management (BR-907) and the permission matrix."""

import pytest
from django.core.management import call_command

from apps.accounts.models import User, UserSession
from apps.accounts.roles import user_roles
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
STAFF = "/api/v1/admin/staff"
USERS = "/api/v1/admin/users"


@pytest.fixture
def admin_client(login_client, super_admin):
    return login_client(super_admin)


@pytest.mark.parametrize("roles", [None, [], ["content_staff"], ["operations_staff"], ["auction_manager"]])
@pytest.mark.parametrize(
    ("method", "path"),
    [("get", STAFF), ("post", STAFF), ("get", USERS), ("get", "/api/v1/admin/roles")],
)
def test_only_super_admin_can_manage_users(roles, method, path, make_user, login_client, api_client):
    client = api_client if roles is None else login_client(make_user(roles=roles))
    response = getattr(client, method)(path, {"phone": "+963955555555", "display_name": "x", "roles": ["super_admin"]})
    assert response.status_code == 403
    assert not User.objects.filter(phone="+963955555555").exists()


def test_create_staff_member(admin_client, super_admin):
    response = admin_client.post(STAFF, {"phone": "0955 555 555", "display_name": "سارة", "roles": ["content_staff"]})
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["phone"] == "+963955555555" and body["is_staff"] and body["roles"] == ["content_staff"]
    entry = AuditLog.objects.get(action="staff.created")
    assert entry.actor == super_admin and entry.changes["roles"] == ["content_staff"]


def test_promoting_an_existing_customer_ends_their_sessions(admin_client, login_client, customer):
    customer_client = login_client(customer)
    response = admin_client.post(STAFF, {"phone": customer.phone, "display_name": "", "roles": ["operations_staff"]})
    assert response.status_code == 201
    assert customer_client.get("/api/v1/auth/me").status_code == 403
    assert AuditLog.objects.filter(action="staff.promoted").exists()


def test_cannot_create_duplicate_staff_or_unknown_role(admin_client, make_user):
    existing = make_user(roles=["content_staff"])
    dup = admin_client.post(STAFF, {"phone": existing.phone, "display_name": "x", "roles": ["content_staff"]})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_STAFF"
    bad = admin_client.post(STAFF, {"phone": "+963966666666", "display_name": "x", "roles": ["god_mode"]})
    assert bad.status_code == 400
    empty = admin_client.post(STAFF, {"phone": "+963966666666", "display_name": "x", "roles": []})
    assert empty.status_code == 400


def test_update_roles_is_audited(admin_client, make_user):
    staff = make_user(roles=["content_staff"])
    response = admin_client.patch(f"{STAFF}/{staff.public_id}", {"roles": ["content_staff", "auction_manager"]})
    assert response.status_code == 200
    assert response.json()["roles"] == ["auction_manager", "content_staff"]
    assert AuditLog.objects.get(action="staff.updated").changes["roles"]["from"] == ["content_staff"]


def test_super_admin_cannot_change_own_roles_or_deactivate_self(admin_client, super_admin):
    r1 = admin_client.patch(f"{STAFF}/{super_admin.public_id}", {"roles": ["content_staff"]})
    r2 = admin_client.post(f"{USERS}/{super_admin.public_id}/deactivate", {})
    r3 = admin_client.delete(f"{STAFF}/{super_admin.public_id}")
    assert {r1.status_code, r2.status_code, r3.status_code} == {409}
    assert user_roles(super_admin) == ["super_admin"]


def test_last_super_admin_cannot_be_removed(super_admin, make_user):
    """Defence in depth at the service layer (the API also blocks self-modification first)."""
    from apps.accounts.errors import LastSuperAdminError
    from apps.accounts.services import users as svc

    operator = make_user(roles=["operations_staff"])
    with pytest.raises(LastSuperAdminError):
        svc.update_staff(actor=operator, target=super_admin, display_name=None, roles=["content_staff"], ip=None)
    with pytest.raises(LastSuperAdminError):
        svc.set_user_active(actor=operator, target=super_admin, active=False, reason="", ip=None)
    with pytest.raises(LastSuperAdminError):
        svc.revoke_staff_access(actor=operator, target=super_admin, ip=None)

    second = make_user(roles=["super_admin"])
    svc.update_staff(actor=second, target=super_admin, display_name=None, roles=["content_staff"], ip=None)
    assert user_roles(super_admin) == ["content_staff"]


def test_revoke_staff_access(admin_client, login_client, make_user):
    staff = make_user(roles=["operations_staff"])
    staff_client = login_client(staff)
    response = admin_client.delete(f"{STAFF}/{staff.public_id}")
    assert response.status_code == 200 and response.json()["is_staff"] is False
    assert staff_client.get("/api/v1/auth/me").status_code == 403
    staff.refresh_from_db()
    assert user_roles(staff) == [] and staff.groups.count() == 0


def test_deactivate_and_reactivate_user(admin_client, login_client, customer):
    customer_client = login_client(customer)
    response = admin_client.post(f"{USERS}/{customer.public_id}/deactivate", {"reason": "إساءة استخدام"})
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert customer_client.get("/api/v1/auth/me").status_code == 403
    assert UserSession.objects.get(user=customer).revoked_reason == "deactivated"
    assert AuditLog.objects.get(action="user.deactivated").reason == "إساءة استخدام"
    assert admin_client.post(f"{USERS}/{customer.public_id}/activate", {}).json()["is_active"] is True


def test_admin_revokes_all_sessions(admin_client, login_client, customer):
    login_client(customer)
    login_client(customer)
    response = admin_client.post(f"{USERS}/{customer.public_id}/revoke-sessions")
    assert response.json() == {"revoked": 2}


def test_user_search_and_filters(admin_client, make_user):
    make_user(phone="+963911222333", display_name="ليلى")
    make_user(phone="+963944555666", display_name="عمر", roles=["content_staff"])
    make_user(phone="+963977888999", display_name="هدى", active=False)

    def names(**params):
        return sorted(u["display_name"] for u in admin_client.get(USERS, params).json()["results"])

    assert names(search="ليلى") == ["ليلى"]
    assert names(search="222") == ["ليلى"]
    assert names(kind="staff") == ["المدير", "عمر"]
    assert names(kind="customer", is_active="false") == ["هدى"]


def test_unknown_user_is_404(admin_client):
    assert admin_client.post(f"{USERS}/00000000-0000-0000-0000-000000000000/deactivate", {}).status_code == 404


def test_bootstrap_super_admin_command(capsys):
    call_command("bootstrap_super_admin", phone="0933 000 111", name="زينة")
    user = User.objects.get(phone="+963933000111")
    assert user.is_staff and user_roles(user) == ["super_admin"]
    assert "+963•••111" in capsys.readouterr().out
    assert AuditLog.objects.filter(action="staff.bootstrap_super_admin", actor=None).exists()


def test_audit_log_is_append_only(admin_client):
    admin_client.post(STAFF, {"phone": "+963955555555", "display_name": "x", "roles": ["content_staff"]})
    entry = AuditLog.objects.get()
    entry.reason = "tampered"
    with pytest.raises(RuntimeError):
        entry.save()
    with pytest.raises(RuntimeError):
        entry.delete()


def test_new_staff_requires_a_name(admin_client):
    response = admin_client.post(STAFF, {"phone": "+963966666666", "roles": ["content_staff"]})
    assert response.status_code == 400 and response.json()["error"]["code"] == "NAME_REQUIRED"
