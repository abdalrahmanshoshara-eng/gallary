from apps.accounts.events import SessionRevoked

from ..protocol import RealtimeMessage
from ..registry import register


def session_group(public_id) -> str:
    return f"session.{public_id}"


def user_group(user_id: int) -> str:
    return f"user.{user_id}"


@register(SessionRevoked)
def session_revoked(event: SessionRevoked):
    # Delivered to every socket opened with that session; consumers close with 4409.
    yield RealtimeMessage(group=session_group(event.session_public_id), type="session.revoked")
