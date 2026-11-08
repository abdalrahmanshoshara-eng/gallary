"""Seed the four pages. The deposit policy's first version is the exact text customers have
accepted since Phase 5 (code 2026-11-05), so stored orders keep matching their version."""

from django.db import migrations

POLICY_V1 = "\n".join(
    f"- {line}"
    for line in [
        "تأكيد الطلب يحجز القطع لك لمدة 24 ساعة.",
        "يُثبَّت الطلب بدفع العربون خلال هذه المهلة؛ بعدها ينتهي الحجز تلقائياً وتعود القطع للعرض.",
        "يُدفع العربون والمبلغ المتبقي بالتنسيق مع فريق المنصة (WhatsApp)، ولا يتم أي دفع عبر الموقع.",
        "يمكنك إلغاء الطلب من حسابك ما دام العربون لم يُدفع.",
        "إذا ألغيت الطلب بعد دفع العربون فإن العربون غير مسترد.",
        "إذا ألغت المنصة الطلب لأي سبب يُعاد إليك العربون كاملاً.",
    ]
)

# Proposed next version (a draft for the Super Admin to review): adds the auction rules.
POLICY_DRAFT = POLICY_V1 + """

## المزادات

- المزايدة ملزمة ولا يمكن سحبها.
- يدفع الفائز عربون التثبيت المعلن في المزاد (50% على الأقل من السعر النهائي) خلال ساعة من إعلان النتيجة.
- إن لم يُدفع العربون خلال المهلة يسقط حق الفائز، ويُعرض العمل على المزايد التالي أو يُلغى البيع حسب شروط المزاد.
- إذا ألغت المنصة المزاد بعد إعلان الفائز يُعاد إليه ما دفعه كاملاً."""

ABOUT = """منصة الفن الدمشقية معرض فني رقمي يجمع اللوحات والمنحوتات والأعمال اليدوية لفنانين نتعاون معهم مباشرة.

## ما نقدّمه

- **أعمال مختارة بعناية**: كل عمل يُراجَع ويُنشر من قِبل فريق المنصة بعد الاتفاق مع الفنان أو المالك.
- **مزادات حيّة**: بتحديث لحظي، والوقت والسعر الرسميان هما ما يعرضه الخادم.
- **أرشيف دائم**: الأعمال المباعة تبقى جزءاً من ذاكرة المنصة الفنية.

## كيف يتم الشراء

نحجز لك القطع عند تأكيد الطلب، ونتواصل معك عبر WhatsApp لترتيب العربون والدفع والتسليم. لا يتم أي دفع عبر الموقع."""

TERMS_DRAFT = """> مسودة للمراجعة القانونية قبل النشر.

## استخدام المنصة

## الحسابات

## الطلبات والدفع

## المزادات

## الملكية الفكرية

## تعديل الشروط"""

PRIVACY_DRAFT = """> مسودة للمراجعة القانونية قبل النشر.

## البيانات التي نجمعها

الاسم، ورقم الهاتف، والبريد الإلكتروني، وعنوان السكن، وتفاصيل الطلبات والمزايدات.

## كيف نستخدمها

## من يطّلع عليها

## حقوقك"""


def seed(apps, schema_editor):
    Page = apps.get_model("cms", "Page")
    PageVersion = apps.get_model("cms", "PageVersion")

    def publish(page, code, title, body):
        version = PageVersion.objects.create(page=page, number=1, code=code, title=title, body=body)
        page.published = version
        page.save(update_fields=["published"])

    policy = Page.objects.create(slug="deposit-policy", draft_title="سياسة العربون والإلغاء", draft_body=POLICY_DRAFT)
    publish(policy, "2026-11-05", "سياسة العربون والإلغاء", POLICY_V1)
    about = Page.objects.create(slug="about", draft_title="من نحن", draft_body=ABOUT)
    publish(about, "2026-11-08", "من نحن", ABOUT)
    Page.objects.create(slug="terms", draft_title="شروط الاستخدام", draft_body=TERMS_DRAFT)
    Page.objects.create(slug="privacy", draft_title="سياسة الخصوصية", draft_body=PRIVACY_DRAFT)


def unseed(apps, schema_editor):
    Page = apps.get_model("cms", "Page")
    Page.objects.update(published=None)
    apps.get_model("cms", "PageVersion").objects.all().delete()
    Page.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("cms", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
