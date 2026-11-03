"""Session policy middleware (BR-908, BR-909)."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import SessionRevokeReason, UserSession
from apps.accounts.services.sessions import revoke_session, revoked_cache_key

pytestmark = pytest.mark.django_db
ME = "/api/v1/auth/me"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def test_revocation_is_immediate_through_the_cache(login_client, customer):
    client = login_client(customer)
    revoke_session(UserSession.objects.get(), SessionRevokeReason.ADMIN)
    assert client.get(ME).status_code == 403


def test_revocation_holds_even_if_the_cache_is_lost(login_client, customer):
    with freeze_time("2026-11-03 10:00:00"):
        client = login_client(customer)
        tracked = UserSession.objects.get()
        revoke_session(tracked, SessionRevokeReason.ADMIN)
        cache.delete(revoked_cache_key(str(tracked.public_id)))
    # The periodic database re-check (every 5 minutes) still catches it.
    with freeze_time("2026-11-03 10:05:01"):
        assert client.get(ME).status_code == 403


def test_staff_session_ends_after_idle_timeout(login_client, make_user):
    staff = make_user(roles=["operations_staff"])
    with freeze_time("2026-11-03 10:00:00"):
        client = login_client(staff)
        assert UserSession.objects.get().is_staff_session
    with freeze_time("2026-11-03 10:20:00"):
        assert client.get(ME).status_code == 200  # activity resets the idle timer
    with freeze_time("2026-11-03 10:49:00"):
        assert client.get(ME).status_code == 200
    with freeze_time("2026-11-03 11:20:00"):
        assert client.get(ME).status_code == 403
    assert UserSession.objects.get().revoked_reason == SessionRevokeReason.EXPIRED


def test_staff_session_has_an_absolute_limit(login_client, make_user):
    staff = make_user(roles=["content_staff"])
    start = timezone.now()
    with freeze_time(start):
        client = login_client(staff)
    for minutes in range(20, 12 * 60, 20):  # active every 20 minutes
        with freeze_time(start + timedelta(minutes=minutes)):
            assert client.get(ME).status_code == 200
    with freeze_time(start + timedelta(hours=12, minutes=1)):
        assert client.get(ME).status_code == 403


def test_customer_session_slides(login_client, customer):
    start = timezone.now()
    with freeze_time(start):
        client = login_client(customer)
    with freeze_time(start + timedelta(days=20)):
        assert client.get(ME).status_code == 200
        tracked = UserSession.objects.get()
        assert tracked.expires_at > start + timedelta(days=45)
    with freeze_time(start + timedelta(days=40)):
        assert client.get(ME).status_code == 200


def test_privilege_change_forces_new_login(login_client, customer):
    client = login_client(customer)
    customer.is_staff = True
    customer.save(update_fields=["is_staff"])
    assert client.get(ME).status_code == 403
    assert UserSession.objects.get().revoked_reason == SessionRevokeReason.ROLE_CHANGED


def test_last_seen_is_written_at_most_every_five_minutes(login_client, customer):
    with freeze_time("2026-11-03 10:00:00"):
        client = login_client(customer)
    with freeze_time("2026-11-03 10:02:00"):
        client.get(ME)
        assert UserSession.objects.get().last_seen_at.minute == 0
    with freeze_time("2026-11-03 10:06:00"):
        client.get(ME)
        assert UserSession.objects.get().last_seen_at.minute == 6
