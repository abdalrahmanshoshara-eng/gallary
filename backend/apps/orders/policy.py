"""
Deposit and cancellation policy shown before checkout (BR-313). The text lives in the CMS
(`deposit-policy` page); the published version's code is stored with each order.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.cms import services as cms_services

RESERVATION_HOURS = 24  # BR-306 (fixed)

# The text customers accepted until the policy moved to the CMS (version 2026-11-05). It seeds
# the CMS page and is the fallback while no version is published (e.g. a fresh database).
DEFAULT_CODE = "2026-11-05"
DEFAULT_TITLE = "سياسة العربون والإلغاء"
DEFAULT_POINTS = [
    "تأكيد الطلب يحجز القطع لك لمدة 24 ساعة.",
    "يُثبَّت الطلب بدفع العربون خلال هذه المهلة؛ بعدها ينتهي الحجز تلقائياً وتعود القطع للعرض.",
    "يُدفع العربون والمبلغ المتبقي بالتنسيق مع فريق المنصة (WhatsApp)، ولا يتم أي دفع عبر الموقع.",
    "يمكنك إلغاء الطلب من حسابك ما دام العربون لم يُدفع.",
    "إذا ألغيت الطلب بعد دفع العربون فإن العربون غير مسترد.",
    "إذا ألغت المنصة الطلب لأي سبب يُعاد إليك العربون كاملاً.",
]
DEFAULT_BODY = "\n".join(f"- {point}" for point in DEFAULT_POINTS)


@dataclass(frozen=True)
class Policy:
    code: str
    title: str
    body: str  # limited Markdown (F-CMS)


def current() -> Policy:
    """The published deposit policy from the CMS (managed by the Super Admin, BR-313)."""
    version = cms_services.published_policy()
    if version is None:
        return Policy(DEFAULT_CODE, DEFAULT_TITLE, DEFAULT_BODY)
    return Policy(version.code, version.title, version.body)


def current_version() -> str:
    return current().code
