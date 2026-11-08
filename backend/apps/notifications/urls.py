from django.urls import path

from .api import views

urls = [
    path("notifications", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/unread-count", views.UnreadCountView.as_view(), name="notifications-unread-count"),
    path("notifications/read-all", views.ReadAllView.as_view(), name="notifications-read-all"),
    path("notifications/preferences", views.PreferencesView.as_view(), name="notifications-preferences"),
    path("notifications/<uuid:public_id>/read", views.NotificationReadView.as_view(), name="notification-read"),
]
