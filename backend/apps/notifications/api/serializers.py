from rest_framework import serializers

from ..models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "category", "title", "body", "link", "created_at", "read_at", "is_read"]
        read_only_fields = fields

    def get_is_read(self, obj: Notification) -> bool:
        return obj.read_at is not None


class UnreadCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()


class ReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    unread = serializers.IntegerField()


class PreferencesSerializer(serializers.Serializer):
    email_enabled = serializers.BooleanField()
    #: The platform sends e-mail at all (SMTP configured and switched on).
    email_available = serializers.BooleanField(read_only=True)
    #: The account has an e-mail address to send to.
    has_email = serializers.BooleanField(read_only=True)
