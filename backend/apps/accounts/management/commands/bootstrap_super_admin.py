"""
Create (or promote) the first Super Admin, who then creates every other staff account
from the admin panel (BR-907). Login is by OTP like everyone else.

    python manage.py bootstrap_super_admin --phone +9639XXXXXXXX --name "الاسم"
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.phone import InvalidPhoneError, mask_phone
from apps.accounts.services.users import bootstrap_super_admin


class Command(BaseCommand):
    help = "Create or promote the first Super Admin (phone-based, OTP login)."

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True)
        parser.add_argument("--name", default="")

    def handle(self, *args, phone: str, name: str, **options):
        try:
            user, created = bootstrap_super_admin(raw_phone=phone, display_name=name)
        except InvalidPhoneError as exc:
            raise CommandError(exc.message) from exc
        verb = "Created" if created else "Promoted"
        self.stdout.write(self.style.SUCCESS(f"{verb} Super Admin {mask_phone(user.phone)}"))
