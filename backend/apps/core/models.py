"""Platform-wide settings editable by the Super Admin (ERD: SiteSetting singleton)."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DepositType(models.TextChoices):
    FIXED = "fixed", "مبلغ ثابت (USD)"
    PERCENTAGE = "percentage", "نسبة من قيمة الطلب"


class SiteSetting(models.Model):
    """Exactly one row (pk=1). Read with `SiteSetting.load()`."""

    default_commission_rate = models.DecimalField(
        "نسبة العمولة الافتراضية %",
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    default_deposit_type = models.CharField(
        "نوع العربون الافتراضي", max_length=12, choices=DepositType.choices, default=DepositType.PERCENTAGE
    )
    default_deposit_value = models.DecimalField(
        "قيمة العربون الافتراضية", max_digits=12, decimal_places=2, default=Decimal("30.00")
    )
    whatsapp_number = models.CharField("رقم WhatsApp للطلبات", max_length=16, blank=True)
    max_pending_orders_per_user = models.PositiveSmallIntegerField("الحد الأقصى للحجوزات المعلقة", default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "إعدادات المنصة"
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="site_setting_singleton"),
            models.CheckConstraint(
                condition=models.Q(default_commission_rate__gte=0, default_commission_rate__lte=100),
                name="site_setting_commission_range",
            ),
            models.CheckConstraint(
                condition=models.Q(default_deposit_value__gt=0), name="site_setting_deposit_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(default_deposit_type="percentage") | models.Q(default_deposit_value__lte=100),
                name="site_setting_deposit_percentage_range",
            ),
        ]

    def __str__(self) -> str:
        return "إعدادات المنصة"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> SiteSetting:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
