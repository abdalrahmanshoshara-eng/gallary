"""`manage.py send_test_email you@example.com` — checks the SMTP settings at deployment."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send one test e-mail with the configured EMAIL_* settings."

    def add_arguments(self, parser):
        parser.add_argument("to")

    def handle(self, *args, **options):
        try:
            send_mail(
                "رسالة تجريبية — منصة الفن الدمشقية",
                "إن وصلتك هذه الرسالة فإعدادات البريد تعمل.",
                settings.DEFAULT_FROM_EMAIL,
                [options["to"]],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f"Sending failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Sent to {options['to']} via {settings.EMAIL_BACKEND}"))
