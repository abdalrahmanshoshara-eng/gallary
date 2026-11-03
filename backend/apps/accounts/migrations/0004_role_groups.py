"""Create the staff role groups (PRD §3). Permissions are attached by later phases."""

from django.db import migrations

ROLES = ["content_staff", "operations_staff", "auction_manager", "super_admin"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLES:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_otp_and_sessions"), ("auth", "0012_alter_user_first_name_max_length")]

    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]
