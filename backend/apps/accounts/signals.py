from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import SessionRevokeReason, UserSession
from .services import sessions as svc


@receiver(user_logged_in)
def track_login(sender, request, user, **kwargs):
    if request is not None and hasattr(request, "session"):
        svc.start_session(request, user)


@receiver(user_logged_out)
def track_logout(sender, request, user, **kwargs):
    if request is None or not hasattr(request, "session"):
        return
    public_id = request.session.get(svc.SESSION_ID_KEY)
    if public_id:
        tracked = UserSession.objects.filter(public_id=public_id, revoked_at__isnull=True).first()
        if tracked:
            svc.revoke_session(tracked, SessionRevokeReason.LOGOUT)
