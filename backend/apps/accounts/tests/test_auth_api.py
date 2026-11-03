import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import SessionRevokeReason, User, UserSession
from apps.accounts.otp.senders import get_otp_sender

pytestmark = pytest.mark.django_db
PHONE = "+963944567890"


@pytest.fixture
def fixed_code(monkeypatch):
    monkeypatch.setattr("apps.accounts.services.otp.generate_code", lambda: "482913")
    return "482913"


@pytest.fixture
def browser():
    """A client that enforces CSRF like a real browser."""
    client = APIClient(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    client.credentials(HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value)
    return client


def login(client, django_capture_on_commit_callbacks, code):
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post("/api/v1/auth/otp/request", {"phone": "0944567890"}).status_code == 202
    return client.post("/api/v1/auth/otp/verify", {"phone": "0944567890", "code": code})


def test_full_login_flow_sets_rotated_session(browser, fixed_code, django_capture_on_commit_callbacks):
    response = login(browser, django_capture_on_commit_callbacks, fixed_code)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["created"] is True
    assert body["user"]["phone"] == PHONE
    assert body["user"]["roles"] == [] and body["user"]["is_staff"] is False
    assert settings.SESSION_COOKIE_NAME in response.cookies
    tracked = UserSession.objects.get()
    assert not tracked.is_staff_session and tracked.revoked_at is None

    me = browser.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]


def test_otp_request_response_does_not_reveal_registration(browser, make_user, django_capture_on_commit_callbacks):
    make_user(phone="+963933333333")
    with django_capture_on_commit_callbacks(execute=True):
        known = browser.post("/api/v1/auth/otp/request", {"phone": "+963933333333"})
        unknown = browser.post("/api/v1/auth/otp/request", {"phone": "+963944444444"})
    assert known.status_code == unknown.status_code == 202
    strip = lambda b: {k: v for k, v in b.items() if k != "phone"}  # noqa: E731
    assert strip(known.json()) == strip(unknown.json())


def test_login_endpoints_require_csrf(django_capture_on_commit_callbacks):
    client = APIClient(enforce_csrf_checks=True)
    assert client.post("/api/v1/auth/otp/request", {"phone": PHONE}).status_code == 403
    assert client.post("/api/v1/auth/otp/verify", {"phone": PHONE, "code": "123456"}).status_code == 403


def test_invalid_phone_is_a_400_with_code(browser):
    response = browser.post("/api/v1/auth/otp/request", {"phone": "123"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PHONE"


def test_wrong_code_reports_remaining_attempts(browser, fixed_code, django_capture_on_commit_callbacks):
    response = login(browser, django_capture_on_commit_callbacks, "000000")
    assert response.status_code == 400
    assert response.json()["error"] == {
        **response.json()["error"],
        "code": "OTP_INVALID",
        "details": {"remaining_attempts": 4},
    }
    assert browser.get("/api/v1/auth/me").status_code == 403


@override_settings(OTP_SENDER="disabled")
def test_otp_unavailable_until_whatsapp_is_configured(browser):
    get_otp_sender.cache_clear()
    response = browser.post("/api/v1/auth/otp/request", {"phone": PHONE})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "OTP_UNAVAILABLE"


def test_rate_limit_returns_429_with_retry_after(browser, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        browser.post("/api/v1/auth/otp/request", {"phone": PHONE})
    response = browser.post("/api/v1/auth/otp/request", {"phone": PHONE})
    assert response.status_code == 429
    assert response.json()["error"]["details"]["retry_after_seconds"] > 0


def test_logout_revokes_tracked_session(browser, fixed_code, django_capture_on_commit_callbacks):
    login(browser, django_capture_on_commit_callbacks, fixed_code)
    browser.credentials(HTTP_X_CSRFTOKEN=browser.cookies[settings.CSRF_COOKIE_NAME].value)
    assert browser.post("/api/v1/auth/logout").status_code == 204
    assert UserSession.objects.get().revoked_reason == SessionRevokeReason.LOGOUT
    assert browser.get("/api/v1/auth/me").status_code == 403


def test_authenticated_writes_require_csrf(customer):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(customer)
    assert client.patch("/api/v1/auth/me", {"display_name": "x"}).status_code == 403


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


def test_user_count_unchanged_by_failed_logins(browser, django_capture_on_commit_callbacks):
    login(browser, django_capture_on_commit_callbacks, "000000")
    assert User.objects.count() == 0
