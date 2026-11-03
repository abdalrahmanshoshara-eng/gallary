from __future__ import annotations

from rest_framework import serializers

from ..models import User, UserSession
from ..roles import Role, user_roles


class PhoneInputSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32, trim_whitespace=True)


class VerifyInputSerializer(PhoneInputSerializer):
    code = serializers.CharField(max_length=12, trim_whitespace=True)


class OtpRequestedSerializer(serializers.Serializer):
    phone = serializers.CharField(help_text="E.164 form of the submitted number")
    expires_in_seconds = serializers.IntegerField()
    resend_after_seconds = serializers.IntegerField()
    channel = serializers.CharField()


class MeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    roles = serializers.SerializerMethodField()
    is_super_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "display_name", "email", "is_staff", "roles", "is_super_admin", "date_joined"]
        read_only_fields = fields

    def get_roles(self, user: User) -> list[str]:
        return user_roles(user)

    def get_is_super_admin(self, user: User) -> bool:
        return Role.SUPER_ADMIN in user_roles(user)


class LoginResultSerializer(serializers.Serializer):
    user = MeSerializer()
    created = serializers.BooleanField()


class ProfileUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)


class SessionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = ["id", "user_agent_summary", "ip", "created_at", "last_seen_at", "expires_at", "current"]
        read_only_fields = fields

    def get_current(self, session: UserSession) -> bool:
        return str(session.public_id) == self.context.get("current_session_id")


class RevokedCountSerializer(serializers.Serializer):
    revoked = serializers.IntegerField()


class RoleSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class AdminUserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "display_name", "email", "is_active", "is_staff", "roles", "date_joined", "last_login"]
        read_only_fields = fields

    def get_roles(self, user: User) -> list[str]:
        return user_roles(user)


class RolesField(serializers.ListField):
    child = serializers.ChoiceField(choices=Role.choices)


class StaffCreateSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    # Required for new accounts; optional when promoting an existing user (keeps their name).
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    roles = RolesField(allow_empty=False)


class StaffUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False)
    roles = RolesField(allow_empty=False, required=False)


class ActivationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
