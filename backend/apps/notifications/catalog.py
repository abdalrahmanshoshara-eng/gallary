"""
Every notification kind and its Arabic text (§26). Domain apps pass a kind + parameters;
the text is rendered here once and stored, so old notifications never change.

`email=True` marks the events worth an e-mail copy: they ask the customer to act or report a
decision about their money or request. Frequent, transient events (outbid, ending soon) stay
in-app only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import Category

LOCAL_TZ = ZoneInfo("Asia/Damascus")
MONTHS = (
    "كانون الثاني",
    "شباط",
    "آذار",
    "نيسان",
    "أيار",
    "حزيران",
    "تموز",
    "آب",
    "أيلول",
    "تشرين الأول",
    "تشرين الثاني",
    "كانون الأول",
)
LRI, PDI = "⁦", "⁩"


def usd(value: Decimal | str | int | float) -> str:
    """`1,250 US$` (cents only when present), bidi-isolated like the web app's formatUsd."""
    amount = Decimal(str(value))
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    return f"{LRI}{text} US${PDI}"


def when(value: datetime | str) -> str:
    """`8 تشرين الثاني، 2:30 م` in Damascus time (Latin digits, platform convention)."""
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    if timezone.is_naive(moment):
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(LOCAL_TZ)
    hour = local.hour % 12 or 12
    suffix = "ص" if local.hour < 12 else "م"
    return f"{local.day} {MONTHS[local.month - 1]}، {hour}:{local.minute:02d} {suffix}"


Text = str | Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class Kind:
    category: str
    title: Text
    body: Text
    email: bool = False

    def render(self, params: dict[str, Any]) -> tuple[str, str]:
        def text(value: Text) -> str:
            return value(params) if callable(value) else value.format(**params)

        return text(self.title)[:200], text(self.body)


def _cancelled_by_platform(p: dict[str, Any]) -> str:
    lines = [f"السبب: {p['reason']}"]
    if p.get("refund_due"):
        lines.append("سنعيد إليك ما دفعته، ويتواصل معك فريقنا لترتيب ذلك.")
    return "\n".join(lines)


def _ending_soon(p: dict[str, Any]) -> str:
    lead = "أنت صاحب أعلى مزايدة حالياً." if p.get("leading") else "مزايدتك ليست الأعلى حالياً."
    return f"{lead} ينتهي المزاد عند {p['ends']}."


def _with_message(default: str) -> Callable[[dict[str, Any]], str]:
    return lambda p: p.get("message") or default


KINDS: dict[str, Kind] = {
    # --- orders ---------------------------------------------------------------------------------
    "order.created": Kind(
        Category.ORDER,
        "استلمنا طلبك {number}",
        "ادفع العربون {deposit} قبل {deadline} لتثبيت الحجز. يتواصل معك فريقنا عبر WhatsApp لترتيب الدفع.",
        email=True,
    ),
    "order.deposit_reminder": Kind(
        Category.ORDER,
        "تذكير: مهلة عربون الطلب {number} تنتهي قريباً",
        "ادفع العربون {deposit} قبل {deadline}، وإلا يُلغى الحجز وتعود القطع إلى العرض.",
        email=True,
    ),
    "order.deposit_confirmed": Kind(
        Category.ORDER,
        "تأكّد عربون طلبك {number}",
        "القطع محجوزة لك الآن. المتبقي {remaining} يُدفع عند التسليم أو بالاتفاق مع فريقنا.",
        email=True,
    ),
    "order.payment_pending": Kind(
        Category.ORDER,
        "استلمنا دفعة لطلبك {number}",
        "المدفوع {paid} من {total}، والمتبقي {remaining}.",
    ),
    "order.confirmed": Kind(
        Category.ORDER,
        "اكتمل دفع طلبك {number}",
        "شكراً لك. يتواصل معك فريقنا لترتيب التسليم.",
        email=True,
    ),
    "order.completed": Kind(
        Category.ORDER,
        "اكتمل طلبك {number}",
        "سُلِّم طلبك. نتمنى أن يسعدك العمل.",
        email=True,
    ),
    "order.expired": Kind(
        Category.ORDER,
        "انتهت مهلة عربون الطلب {number}",
        "أُلغي الحجز وعادت القطع إلى العرض. يمكنك الطلب من جديد إن كانت ما تزال متاحة.",
        email=True,
    ),
    "order.cancelled_by_platform": Kind(
        Category.ORDER, "ألغت المنصة طلبك {number}", _cancelled_by_platform, email=True
    ),
    "order.cancelled_for_customer": Kind(
        Category.ORDER,
        "أُلغي طلبك {number} بناءً على طلبك",
        "العربون غير مسترد وفق سياسة العربون والإلغاء.",
        email=True,
    ),
    # --- auctions -------------------------------------------------------------------------------
    "auction.outbid": Kind(
        Category.AUCTION,
        "تم تجاوز مزايدتك في «{title}»",
        "السعر الحالي {price}، وأقل مزايدة تالية {next}.",
    ),
    "auction.ending_soon": Kind(Category.AUCTION, "مزاد «{title}» ينتهي قريباً", _ending_soon),
    "auction.won": Kind(
        Category.AUCTION,
        "فزت بمزاد «{title}»",
        "سعرك {amount}. ادفع العربون {deposit} قبل {deadline} لتثبيت الفوز (الطلب {order}).",
        email=True,
    ),
    "auction.award_lost": Kind(
        Category.AUCTION,
        "سقط حقك في «{title}»",
        "لم يُدفع العربون خلال المهلة، فانتقل العمل وفق شروط المزاد.",
        email=True,
    ),
    "auction.bid_voided": Kind(
        Category.AUCTION,
        "ألغت الإدارة مزايدتك في «{title}»",
        "المزايدة {amount}. السبب: {reason}",
        email=True,
    ),
    "auction.lead_restored": Kind(
        Category.AUCTION,
        "عدت صاحب أعلى مزايدة في «{title}»",
        "بعد إلغاء مزايدة أعلى، صارت مزايدتك {amount} هي الأعلى.",
    ),
    # --- auction requests -----------------------------------------------------------------------
    "request.under_review": Kind(
        Category.REQUEST,
        "طلب المزاد «{title}» قيد المراجعة",
        _with_message("يراجع فريقنا عملك وسنعلمك بالخطوة التالية."),
    ),
    "request.needs_more_info": Kind(
        Category.REQUEST,
        "نحتاج معلومات إضافية عن «{title}»",
        _with_message("افتح الطلب وأكمل المعلومات المطلوبة ليعود إلى المراجعة."),
        email=True,
    ),
    "request.negotiation": Kind(
        Category.REQUEST,
        "بدأ التفاوض على «{title}»",
        _with_message("يتواصل معك فريقنا للاتفاق على شروط المزاد."),
        email=True,
    ),
    "request.approved": Kind(
        Category.REQUEST,
        "قُبل طلب المزاد «{title}»",
        _with_message("سنجهّز العمل للمزاد ونعلمك بموعده."),
        email=True,
    ),
    "request.rejected": Kind(
        Category.REQUEST,
        "لم يُقبل طلب المزاد «{title}»",
        _with_message("شكراً لثقتك. يمكنك إرسال عمل آخر في أي وقت."),
        email=True,
    ),
    "request.message": Kind(Category.REQUEST, "رسالة جديدة بخصوص «{title}»", "{message}", email=True),
    # --- payouts --------------------------------------------------------------------------------
    "payout.paid": Kind(
        Category.PAYOUT,
        "حوّلنا مستحقاتك",
        "المبلغ {amount}، بتاريخ {date}، والمرجع {reference}.",
        email=True,
    ),
}
