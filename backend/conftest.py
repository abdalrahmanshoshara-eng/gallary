import os

import pytest

from apps.core.events import reset_event_bus


def pytest_collection_modifyitems(config, items):
    if os.environ.get("REDIS_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="set REDIS_INTEGRATION=1 to run tests against a real Redis")
    for item in items:
        if "redis" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _fresh_event_bus():
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


# --- accounts fixtures --------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_otp_sender():
    from apps.accounts.otp.senders import get_otp_sender

    get_otp_sender.cache_clear()
    yield
    get_otp_sender.cache_clear()


@pytest.fixture
def make_user(db):
    from apps.accounts.models import User

    counter = iter(range(100, 1000))

    def _make(*, roles=(), phone=None, active=True, **extra):
        from django.contrib.auth.models import Group

        phone = phone or f"+9639{next(counter):08d}"
        user = User.objects.create_user(phone=phone, is_staff=bool(roles), is_active=active, **extra)
        if roles:
            user.groups.add(*Group.objects.filter(name__in=roles))
        return user

    return _make


@pytest.fixture
def customer(make_user):
    return make_user(display_name="عميل")


@pytest.fixture
def super_admin(make_user):
    return make_user(roles=["super_admin"], display_name="المدير")


@pytest.fixture
def login_client():
    """Returns an APIClient logged in through Django's login() (fires our session tracking)."""
    from rest_framework.test import APIClient

    def _login(user):
        client = APIClient()
        client.force_login(user)
        return client

    return _login
