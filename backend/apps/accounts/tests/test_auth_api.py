import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import SessionRevokeReason, User, UserSession
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
PHONE = "+963944567890"
PASSWORD = "Jasmine2026"
REGISTRATION = {
    "phone": "0944 567 890",
    "first_name": "زينة",
    "last_name": "المصري",
    "email": "Zaina@Example.com",
    "governorate": "damascus",
    "city": "المزة",
    "address_line": "شارع الجلاء، بناء 4",
    "password": PASSWORD,
    "password_confirm": PASSWORD,
}


@pytest.fixture(autouse=True)
def _clear_lockouts():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def browser():
    """A client that enforces CSRF like a real browser."""
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    client.credentials(HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)
    return client


def refresh_csrf(client):
    client.credentials(HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)


@pytest.fixture
def member(make_user):
    user = make_user(phone=PHONE)
    user.set_password(PASSWORD)
    user.save()
    return user


# --- registration ------------------------------------------------------------------------------
def test_customer_registers_and_is_signed_in(browser):
    response = browser.post("/api/v1/auth/register", REGISTRATION)
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["phone"] == PHONE and body["display_name"] == "زينة المصري"
    assert body["governorate"] == "damascus" and body["phone_verified"] is False
    assert body["roles"] == [] and body["is_staff"] is False
    user = User.objects.get()
    assert user.email == "Zaina@example.com" and user.check_password(PASSWORD)
    assert UserSession.objects.get(user=user).revoked_at is None
    assert browser.get("/api/v1/auth/me").json()["id"] == body["id"]
    assert AuditLog.objects.filter(action="user.registered").exists()


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"password": "short1", "password_confirm": "short1"}, "password"),
        ({"password": "onlyletters", "password_confirm": "onlyletters"}, "password"),
        ({"password": "1234567890", "password_confirm": "1234567890"}, "password"),
        ({"password_confirm": "Different2026"}, "password_confirm"),
        ({"email": ""}, "email"),
        ({"first_name": ""}, "first_name"),
        ({"governorate": "atlantis"}, "governorate"),
        ({"address_line": ""}, "address_line"),
    ],
)
def test_registration_validation(browser, override, field):
    response = browser.post("/api/v1/auth/register", {**REGISTRATION, **override})
    assert response.status_code == 400
    assert field in response.json()["error"]["details"], response.json()
    assert not User.objects.exists()


def test_registration_rejects_used_phone_and_email(browser, make_user):
    make_user(phone=PHONE)
    assert browser.post("/api/v1/auth/register", REGISTRATION).json()["error"]["code"] == "PHONE_IN_USE"
    make_user(email="zaina@example.com")
    response = browser.post("/api/v1/auth/register", {**REGISTRATION, "phone": "0944567891"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "EMAIL_IN_USE"


def test_registration_cannot_grant_privileges(browser):
    browser.post("/api/v1/auth/register", {**REGISTRATION, "is_staff": True, "roles": ["super_admin"]})
    user = User.objects.get()
    assert not user.is_staff and not user.is_superuser and not user.groups.exists()


# --- login ------------------------------------------------------------------------------------
def test_login_with_phone_and_password_rotates_session(browser, member):
    response = browser.post("/api/v1/auth/login", {"phone": "٠٩٤٤٥٦٧٨٩٠", "password": PASSWORD})
    assert response.status_code == 200, response.json()
    assert response.json()["phone"] == PHONE
    assert settings.SESSION_COOKIE_NAME in response.cookies
    assert UserSession.objects.get(user=member).revoked_at is None


def test_login_errors_do_not_reveal_registered_phones(browser, member):
    wrong = browser.post("/api/v1/auth/login", {"phone": PHONE, "password": "Wrong2026x"})
    unknown = browser.post("/api/v1/auth/login", {"phone": "0933333333", "password": PASSWORD})
    malformed = browser.post("/api/v1/auth/login", {"phone": "123", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == malformed.status_code == 400
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert browser.get("/api/v1/auth/me").status_code == 403


@override_settings(LOGIN_MAX_FAILURES_PER_PHONE=3)
def test_repeated_failures_lock_the_phone(browser, member):
    for _ in range(3):
        browser.post("/api/v1/auth/login", {"phone": PHONE, "password": "Wrong2026x"})
    locked = browser.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD})
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "LOGIN_LOCKED"


def test_deactivated_account_cannot_log_in(browser, member):
    member.is_active = False
    member.save()
    response = browser.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD})
    assert response.status_code == 403 and response.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_account_without_password_cannot_log_in(browser, make_user):
    make_user(phone=PHONE)  # e.g. created by the old OTP flow: unusable password
    response = browser.post("/api/v1/auth/login", {"phone": PHONE, "password": ""})
    assert response.status_code == 400


def test_login_endpoints_require_csrf():
    client = APIClient(enforce_csrf_checks=True)
    assert client.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD}).status_code == 403
    assert client.post("/api/v1/auth/register", REGISTRATION).status_code == 403


def test_otp_login_endpoints_are_gone(browser):
    assert browser.post("/api/v1/auth/otp/request", {"phone": PHONE}).status_code == 404


def test_logout_revokes_tracked_session(browser, member):
    browser.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD})
    refresh_csrf(browser)
    assert browser.post("/api/v1/auth/logout").status_code == 204
    assert UserSession.objects.get().revoked_reason == SessionRevokeReason.LOGOUT
    assert browser.get("/api/v1/auth/me").status_code == 403


def test_authenticated_writes_require_csrf(customer):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(customer)
    assert client.patch("/api/v1/auth/me", {"display_name": "x"}).status_code == 403


# --- password change ------------------------------------------------------------------------------
def test_password_change_keeps_this_device_and_ends_others(browser, member):
    other_device = APIClient()
    other_device.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD})
    browser.post("/api/v1/auth/login", {"phone": PHONE, "password": PASSWORD})
    refresh_csrf(browser)

    wrong = browser.post("/api/v1/auth/password", {"current_password": "nope", "new_password": "NewPass2026"})
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "WRONG_PASSWORD"
    weak = browser.post("/api/v1/auth/password", {"current_password": PASSWORD, "new_password": "123"})
    assert weak.status_code == 400 and "password" in weak.json()["error"]["details"]

    ok = browser.post("/api/v1/auth/password", {"current_password": PASSWORD, "new_password": "NewPass2026"})
    assert ok.status_code == 200 and ok.json() == {"revoked": 1}
    assert browser.get("/api/v1/auth/me").status_code == 200
    assert other_device.get("/api/v1/auth/me").status_code == 403
    member.refresh_from_db()
    assert member.check_password("NewPass2026")


# --- default Super Admin ----------------------------------------------------------------------------
@override_settings(DEFAULT_SUPER_ADMIN_PHONE="0943959774", DEFAULT_SUPER_ADMIN_PASSWORD="admin123456", DEBUG=True)
def test_default_super_admin_is_created_once_and_keeps_a_changed_password(browser):
    call_command("ensure_super_admin")
    admin = User.objects.get(phone="+963943959774")
    assert admin.is_staff and admin.groups.filter(name="super_admin").exists()
    login = browser.post("/api/v1/auth/login", {"phone": "0943959774", "password": "admin123456"})
    assert login.status_code == 200 and login.json()["is_super_admin"] is True

    admin.set_password("Changed2026x")
    admin.save()
    call_command("ensure_super_admin")  # e.g. the next `docker compose up`
    admin.refresh_from_db()
    assert admin.check_password("Changed2026x") and User.objects.count() == 1


@override_settings(DEFAULT_SUPER_ADMIN_PASSWORD="admin123456", DEBUG=False)
def test_production_refuses_the_development_admin_password():
    with pytest.raises(CommandError):
        call_command("ensure_super_admin")
    assert not User.objects.exists()


# --- profile -------------------------------------------------------------------------------
def test_profile_update(login_client, customer):
    client = login_client(customer)
    response = client.patch("/api/v1/auth/me", {"display_name": "  زينة  ", "email": "Zaina@Example.com"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "زينة"
    customer.refresh_from_db()
    assert customer.email == "Zaina@example.com"


def test_profile_email_must_be_unique_case_insensitively(login_client, customer, make_user):
    make_user(email="taken@example.com")
    response = login_client(customer).patch("/api/v1/auth/me", {"email": "TAKEN@example.com"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_IN_USE"


def test_profile_cannot_change_phone_or_privileges(login_client, customer):
    client = login_client(customer)
    client.patch("/api/v1/auth/me", {"phone": "+963999999999", "is_staff": True, "roles": ["super_admin"]})
    customer.refresh_from_db()
    assert customer.phone != "+963999999999" and not customer.is_staff


def test_email_can_be_cleared(login_client, make_user):
    user = make_user(email="a@example.com")
    login_client(user).patch("/api/v1/auth/me", {"email": ""})
    user.refresh_from_db()
    assert user.email is None


# --- sessions --------------------------------------------------------------------------------
def test_sessions_list_marks_current_and_revoke_others(login_client, customer):
    phone_client = login_client(customer)
    laptop_client = login_client(customer)
    sessions = laptop_client.get("/api/v1/auth/sessions").json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1

    assert laptop_client.post("/api/v1/auth/sessions/revoke-others").json() == {"revoked": 1}
    assert phone_client.get("/api/v1/auth/me").status_code == 403
    assert laptop_client.get("/api/v1/auth/me").status_code == 200


def test_revoking_a_specific_session(login_client, customer):
    phone_client = login_client(customer)
    laptop_client = login_client(customer)
    phone_session = next(s for s in phone_client.get("/api/v1/auth/sessions").json() if s["current"])
    assert laptop_client.delete(f"/api/v1/auth/sessions/{phone_session['id']}").status_code == 204
    assert phone_client.get("/api/v1/auth/me").status_code == 403


def test_cannot_revoke_another_users_session(login_client, customer, make_user):
    other = make_user()
    login_client(other)
    other_session = UserSession.objects.get(user=other)
    response = login_client(customer).delete(f"/api/v1/auth/sessions/{other_session.public_id}")
    assert response.status_code == 404
    other_session.refresh_from_db()
    assert other_session.revoked_at is None
