from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "title", "read_at", "email_status", "email_attempts")
    list_filter = ("category", "email_status", "kind")
    search_fields = ("title", "user__phone", "user__email")
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False
