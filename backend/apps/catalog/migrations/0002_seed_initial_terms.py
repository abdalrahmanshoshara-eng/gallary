"""
Initial classification data from PROJECT_MASTER_PROMPT §10. Editable by staff afterwards.
Idempotent (get_or_create by slug); reversing removes only untouched seed rows.
"""

from django.db import migrations

CATEGORIES = [
    ("paintings", "لوحات"),
    ("sculptures", "منحوتات"),
    ("handicrafts", "أعمال يدوية"),
    ("decorative-art", "فن زخرفي"),
    ("mixed-works", "أعمال مختلطة"),
    ("other-categories", "تصنيفات أخرى"),
]
TECHNIQUES = [
    ("oil", "زيت"),
    ("acrylic", "أكريليك"),
    ("watercolor", "مائي"),
    ("encaustic", "شمعي / Encaustic"),
    ("pencil", "قلم رصاص"),
    ("charcoal", "فحم"),
    ("pastel", "باستيل"),
    ("ink", "حبر"),
    ("mixed-techniques", "تقنيات مختلطة"),
    ("other-techniques", "تقنيات أخرى"),
]
MATERIALS = [
    ("wood", "خشب"),
    ("stone", "حجر"),
    ("marble", "رخام"),
    ("clay", "طين"),
    ("pottery", "فخار"),
    ("plaster", "جبس"),
    ("bronze", "برونز"),
    ("copper", "نحاس"),
    ("iron", "حديد"),
    ("resin", "Resin"),
    ("mixed-materials", "مواد مختلطة"),
    ("other-materials", "مواد أخرى"),
]


def seed(apps, schema_editor):
    for model_name, rows in (("Category", CATEGORIES), ("Technique", TECHNIQUES), ("Material", MATERIALS)):
        model = apps.get_model("catalog", model_name)
        for order, (slug, name) in enumerate(rows, start=1):
            model.objects.get_or_create(slug=slug, defaults={"name": name, "sort_order": order * 10})


def unseed(apps, schema_editor):
    for model_name, rows in (("Category", CATEGORIES), ("Technique", TECHNIQUES), ("Material", MATERIALS)):
        model = apps.get_model("catalog", model_name)
        model.objects.filter(slug__in=[slug for slug, _ in rows]).delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
