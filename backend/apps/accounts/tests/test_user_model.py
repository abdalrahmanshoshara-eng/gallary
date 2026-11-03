import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import User


@pytest.mark.django_db
def test_customer_has_no_usable_password():
    user = User.objects.create_user(phone="+963912345678")
    assert not user.has_usable_password()
    assert not user.is_staff and not user.is_superuser


@pytest.mark.django_db
@pytest.mark.parametrize("phone", ["0912345678", "+0912345678", "+963-912", "963912345678"])
def test_phone_must_be_e164(phone):
    with pytest.raises(ValidationError):
        User.objects.create_user(phone=phone)


@pytest.mark.django_db
def test_phone_is_unique():
    User.objects.create_user(phone="+963912345678")
    with pytest.raises(ValidationError):
        User.objects.create_user(phone="+963912345678")


@pytest.mark.django_db
def test_superuser_requires_password():
    with pytest.raises(ValueError):
        User.objects.create_superuser(phone="+963900000001")
    admin = User.objects.create_superuser(phone="+963900000001", password="a-long-admin-passphrase")
    assert admin.is_staff and admin.is_superuser and admin.check_password("a-long-admin-passphrase")


@pytest.mark.django_db
def test_email_is_unique_case_insensitively_at_database_level():
    User.objects.create_user(phone="+963900000002", email="Art@Example.com")
    with pytest.raises(IntegrityError):
        User.objects.bulk_create([User(phone="+963900000003", email="art@example.COM")])
