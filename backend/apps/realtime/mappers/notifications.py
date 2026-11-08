from apps.notifications.events import NotificationCreated

from ..protocol import RealtimeMessage
from ..registry import register
from .accounts import user_group


@register(NotificationCreated)
def notification_created(event: NotificationCreated):
    # The bell refetches the unread count; the payload is enough for a toast if wanted.
    yield RealtimeMessage(
        group=user_group(event.user_id),
        type="notification.created",
        data={"id": event.notification_id, "kind": event.kind, "title": event.title, "link": event.link},
    )
