"""
Create the public and private buckets if they do not exist (development / self-hosted
SeaweedFS). With a managed S3 provider the buckets are created by the operator; the
command is then a no-op check.
"""

from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand, CommandError

from apps.media.storage import private_storage, public_storage


class Command(BaseCommand):
    help = "Ensure the S3 buckets used for media exist."

    def handle(self, *args, **options):
        for storage in (public_storage(), private_storage()):
            client = storage.connection.meta.client
            bucket = storage.bucket_name
            try:
                client.head_bucket(Bucket=bucket)
                self.stdout.write(f"bucket {bucket}: ok")
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise CommandError(f"bucket {bucket}: {code}") from exc
                client.create_bucket(Bucket=bucket)
                self.stdout.write(self.style.SUCCESS(f"bucket {bucket}: created"))
