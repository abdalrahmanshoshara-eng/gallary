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


# --- catalog / media fixtures ----------------------------------------------------------
def make_image_bytes(fmt="JPEG", size=(1200, 800), *, orientation=None, gps=False, mode="RGB", color=(150, 90, 60)):
    """Real encoded image bytes, optionally with EXIF orientation and GPS metadata."""
    import io

    from PIL import Image

    image = Image.new(mode, size, color if mode == "RGB" else (*color, 128))
    buffer = io.BytesIO()
    kwargs = {}
    if fmt == "JPEG" and (orientation or gps):
        exif = Image.Exif()
        if orientation:
            exif[0x0112] = orientation
        if gps:
            exif[0x8825] = {1: "N", 2: (33.0, 30.0, 0.0), 3: "E", 4: (36.0, 18.0, 0.0)}
        kwargs["exif"] = exif.tobytes()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


@pytest.fixture
def image_file():
    from django.core.files.uploadedfile import SimpleUploadedFile

    def _make(name="art.jpg", fmt="JPEG", **kwargs):
        content_types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        return SimpleUploadedFile(
            name, make_image_bytes(fmt, **kwargs), content_type=content_types.get(fmt, "image/jpeg")
        )

    return _make


@pytest.fixture
def content_staff(make_user):
    return make_user(roles=["content_staff"], display_name="محررة")


@pytest.fixture
def category(db):
    from apps.catalog.models import Category

    return Category.objects.get(slug="paintings")


@pytest.fixture
def artist_factory(db):
    from apps.artists.models import Artist

    counter = iter(range(1, 10_000))

    def _make(**extra):
        n = next(counter)
        return Artist.objects.create(
            name=extra.pop("name", f"فنان {n}"), slug=extra.pop("slug", f"artist-{n}"), **extra
        )

    return _make


@pytest.fixture
def artwork_factory(db, category, artist_factory, django_capture_on_commit_callbacks):
    """Creates artworks; `published=True` attaches a processed image and publishes."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.artworks import services
    from apps.artworks.models import Artwork

    counter = iter(range(1, 10_000))

    def _make(*, published=False, artist=..., **extra):
        n = next(counter)
        if artist is ...:
            artist = artist_factory()
        artwork = Artwork.objects.create(
            title=extra.pop("title", f"عمل {n}"),
            slug=extra.pop("slug", f"artwork-{n}"),
            category=extra.pop("category", category),
            artist=artist,
            **extra,
        )
        if published:
            with django_capture_on_commit_callbacks(execute=True):
                services.add_image(artwork, SimpleUploadedFile("a.jpg", make_image_bytes()), actor=None)
            services.publish(artwork, actor=None)
            artwork.refresh_from_db()
        return artwork

    return _make
