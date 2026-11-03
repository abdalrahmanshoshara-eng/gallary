"""Add User.public_id safely for tables that already contain rows (ADR-13)."""

import uuid

from django.db import migrations, models


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(public_id__isnull=True).only("pk").iterator():
        User.objects.filter(pk=user.pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(model_name="user", name="public_id", field=models.UUIDField(null=True, editable=False)),
        migrations.RunPython(backfill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
