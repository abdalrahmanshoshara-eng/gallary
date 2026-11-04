"""
Create the default Super Admin when its phone has no account yet (run by the migrate service).

Phone/password/name come from DEFAULT_SUPER_ADMIN_* settings. An existing account keeps its
password, so changing it from the account page is permanent. Outside DEBUG the development
password is refused: production must set its own strong DEFAULT_SUPER_ADMIN_PASSWORD.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.phone import InvalidPhoneError, mask_phone
from apps.accounts.services.auth import DEV_DEFAULT_PASSWORD, ensure_super_admin


class Command(BaseCommand):
    help = "Create the default Super Admin (phone + password) if it does not exist."

    def handle(self, *args, **options):
        password = settings.DEFAULT_SUPER_ADMIN_PASSWORD
        if not settings.DEBUG:
            if not password or password == DEV_DEFAULT_PASSWORD:
                raise CommandError(
                    "Set a strong DEFAULT_SUPER_ADMIN_PASSWORD in production (the development default is refused)."
                )
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(password, user=User(phone=settings.DEFAULT_SUPER_ADMIN_PHONE))
            except ValidationError as exc:
                raise CommandError("DEFAULT_SUPER_ADMIN_PASSWORD: " + " ".join(exc.messages)) from exc
        try:
            user, created = ensure_super_admin(
                raw_phone=settings.DEFAULT_SUPER_ADMIN_PHONE,
                password=password,
                display_name=settings.DEFAULT_SUPER_ADMIN_NAME,
            )
        except InvalidPhoneError as exc:
            raise CommandError(exc.message) from exc
        state = "created" if created else "already present"
        self.stdout.write(self.style.SUCCESS(f"Super Admin {mask_phone(user.phone)}: {state}"))
