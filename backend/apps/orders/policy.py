"""
Deposit and cancellation policy shown before checkout (BR-313). The customer's acceptance
is stored with the version; change VERSION whenever the text changes.
"""

VERSION = "2026-11-05"
RESERVATION_HOURS = 24  # BR-306 (fixed)

TITLE = "سياسة العربون والإلغاء"
POINTS = [
    "تأكيد الطلب يحجز القطع لك لمدة 24 ساعة.",
    "يُثبَّت الطلب بدفع العربون خلال هذه المهلة؛ بعدها ينتهي الحجز تلقائياً وتعود القطع للعرض.",
    "يُدفع العربون والمبلغ المتبقي بالتنسيق مع فريق المنصة (WhatsApp)، ولا يتم أي دفع عبر الموقع.",
    "يمكنك إلغاء الطلب من حسابك ما دام العربون لم يُدفع.",
    "إذا ألغيت الطلب بعد دفع العربون فإن العربون غير مسترد.",
    "إذا ألغت المنصة الطلب لأي سبب يُعاد إليك العربون كاملاً.",
]
