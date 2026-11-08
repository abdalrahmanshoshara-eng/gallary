from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from celery.exceptions import Retry
from django.core import mail
from django.utils import timezone

from apps.core.events import get_event_bus
from apps.notifications import channels, services, tasks
from apps.notifications.catalog import usd, when
from apps.notifications.events import NotificationCreated
from apps.notifications.models import EmailStatus, Notification

pytestmark = pytest.mark.django_db
API = "/api/v1/notifications"
PARAMS = {"number": "ART-2026-000042", "deposit": usd("300"), "deadline": "9 تشرين الثاني، 2:30 م"}


@pytest.fixture
def reader(make_user):
    return make_user(display_name="ريم", email="reem@example.com")


def make(user, kind="order.created", params=PARAMS, **kw):
    return services.notify(user, kind, params=params, link="/orders/ART-2026-000042", **kw)


def test_formatting_matches_the_web_app():
    assert usd("1250") == "⁦1,250 US$⁩"
    assert usd(Decimal("99.5")) == "⁦99.50 US$⁩"
    # Damascus is UTC+3: 11:30 UTC → 2:30 PM local, Latin digits, Arabic month.
    assert when(datetime(2026, 11, 9, 11, 30, tzinfo=UTC)) == "9 تشرين الثاني، 2:30 م"
    assert when("2026-01-01T06:05:00+00:00") == "1 كانون الثاني، 9:05 ص"


def test_notify_stores_a_snapshot_and_mails_a_copy_after_commit(reader, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        n = make(reader)
        assert not mail.outbox  # nothing leaves before the event's transaction commits
    n.refresh_from_db()
    assert n.title == "استلمنا طلبك ART-2026-000042" and "300 US$" in n.body
    assert n.category == "order" and n.read_at is None
    assert n.email_status == EmailStatus.SENT and n.email_attempts == 1 and n.email_sent_at
    [message] = mail.outbox
    assert message.to == ["reem@example.com"]
    assert message.subject.startswith("استلمنا طلبك ART-2026-000042 — ")
    assert "https://art.test/orders/ART-2026-000042" in message.body
    assert "https://art.test/notifications" in message.body  # how to stop e-mails
    html = message.alternatives[0][0]
    assert 'dir="rtl"' in html and 'href="https://art.test/orders/ART-2026-000042"' in html
    [event] = [e for e in get_event_bus().events if isinstance(e, NotificationCreated)]
    assert event.user_id == reader.pk and event.notification_id == str(n.public_id)


def test_html_escapes_user_text(reader, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.notify(reader, "request.message", params={"title": "<b>x</b>", "message": "<script>1</script>"})
    html = mail.outbox[0].alternatives[0][0]
    assert "<script>" not in html and "&lt;script&gt;" in html


@pytest.mark.parametrize(
    ("case", "kind"),
    [("no address", "order.created"), ("opted out", "order.created"), ("in-app kind", "auction.outbid")],
)
def test_no_email_when_not_wanted(case, kind, make_user, django_capture_on_commit_callbacks):
    user = make_user(email=None if case == "no address" else "a@example.com")
    if case == "opted out":
        services.set_email_enabled(user, False)
    params = {"title": "t", "price": "1", "next": "2"} if kind == "auction.outbid" else PARAMS
    with django_capture_on_commit_callbacks(execute=True):
        n = services.notify(user, kind, params=params)
    assert n.email_status == EmailStatus.NONE and not mail.outbox


def test_no_email_when_the_platform_has_it_switched_off(reader, settings, django_capture_on_commit_callbacks):
    settings.NOTIFICATIONS_EMAIL_ENABLED = False
    with django_capture_on_commit_callbacks(execute=True):
        n = make(reader)
    assert n.email_status == EmailStatus.NONE and not mail.outbox


def test_dedupe_key_sends_once(reader):
    assert make(reader, dedupe_key="order.deposit_reminder:ART-1") is not None
    assert make(reader, dedupe_key="order.deposit_reminder:ART-1") is None
    assert Notification.objects.filter(user=reader).count() == 1


def test_mail_is_claimed_so_a_redelivered_task_sends_once(reader, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        n = make(reader)
    tasks.send_notification_email.apply(args=[n.pk])
    assert len(mail.outbox) == 1


def test_failures_retry_then_stop(reader, monkeypatch):
    n = make(reader)  # no commit callbacks run: the mail is still pending

    class Broken(channels.EmailSender):
        def send(self, message):
            raise channels.EmailDeliveryError("connection refused")

    monkeypatch.setattr(tasks, "get_email_sender", lambda: Broken())
    with pytest.raises(Retry):
        tasks.send_notification_email.apply(args=[n.pk], throw=True)
    n.refresh_from_db()
    assert (n.email_status, n.email_attempts, n.email_error) == (EmailStatus.PENDING, 1, "connection refused")
    Notification.objects.filter(pk=n.pk).update(email_attempts=services.MAX_EMAIL_ATTEMPTS - 1)
    tasks.send_notification_email.apply(args=[n.pk], throw=True)
    n.refresh_from_db()
    assert n.email_status == EmailStatus.FAILED and n.email_attempts == services.MAX_EMAIL_ATTEMPTS
    assert not mail.outbox


def test_api_lists_counts_and_marks_read(reader, make_user, login_client):
    other = make_user()
    first = make(reader)
    second = services.notify(reader, "order.completed", params={"number": "ART-2026-000042"})
    foreign = make(other)
    client = login_client(reader)

    listed = client.get(API).json()
    assert [r["id"] for r in listed["results"]] == [str(second.public_id), str(first.public_id)]
    assert listed["results"][0]["is_read"] is False and listed["results"][1]["link"] == "/orders/ART-2026-000042"
    assert client.get(f"{API}/unread-count").json() == {"unread": 2}

    read = client.post(f"{API}/{first.public_id}/read")
    assert read.status_code == 200 and read.json()["is_read"] is True
    assert client.post(f"{API}/{first.public_id}/read").json()["read_at"] == read.json()["read_at"]  # idempotent
    assert [r["id"] for r in client.get(f"{API}?unread=1").json()["results"]] == [str(second.public_id)]
    assert client.post(f"{API}/{foreign.public_id}/read").status_code == 404  # never another user's

    assert client.post(f"{API}/read-all").json() == {"updated": 1, "unread": 0}
    assert client.get(f"{API}/unread-count").json() == {"unread": 0}
    assert Notification.objects.get(pk=foreign.pk).read_at is None


def test_preferences(reader, make_user, login_client, settings):
    client = login_client(reader)
    assert client.get(f"{API}/preferences").json() == {
        "email_enabled": True,
        "email_available": True,
        "has_email": True,
    }
    off = client.patch(f"{API}/preferences", {"email_enabled": False}, format="json")
    assert off.status_code == 200 and off.json()["email_enabled"] is False
    assert make(reader).email_status == EmailStatus.NONE

    no_address = login_client(make_user(email=None)).get(f"{API}/preferences").json()
    assert no_address["has_email"] is False
    settings.NOTIFICATIONS_EMAIL_ENABLED = False
    assert client.get(f"{API}/preferences").json()["email_available"] is False


def test_anonymous_gets_nothing(api_client):
    assert api_client.get(API).status_code in (401, 403)
    assert api_client.get(f"{API}/unread-count").status_code in (401, 403)


def test_staff_accounts_have_notifications_too(make_user, login_client):
    staff = make_user(roles=["operations_staff"])
    make(staff)
    assert login_client(staff).get(f"{API}/unread-count").json() == {"unread": 1}


def test_sweep_drops_old_read_and_requeues_stuck_mail(reader, settings):
    now = timezone.now()
    old_read = make(reader)
    old_unread = services.notify(reader, "order.completed", params={"number": "A"})
    Notification.objects.filter(pk__in=[old_read.pk, old_unread.pk]).update(
        created_at=now - timedelta(days=settings.NOTIFICATIONS_RETENTION_DAYS + 1)
    )
    Notification.objects.filter(pk=old_read.pk).update(read_at=now)
    stuck = services.notify(reader, "order.completed", params={"number": "B"})
    Notification.objects.filter(pk=stuck.pk).update(
        email_status=EmailStatus.SENDING, created_at=now - timedelta(minutes=30)
    )

    assert services.sweep(now) == {"deleted": 1, "requeued": 1}
    assert Notification.objects.filter(pk=old_unread.pk).exists()  # unread is never dropped
    stuck.refresh_from_db()
    assert stuck.email_status == EmailStatus.SENT and len(mail.outbox) == 1
