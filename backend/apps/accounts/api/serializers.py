from __future__ import annotations

from rest_framework import serializers

from ..models import Governorate, User, UserSession
from ..roles import Role, user_roles


class PhoneInputSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32, trim_whitespace=True)


class LoginInputSerializer(PhoneInputSerializer):
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class RegisterInputSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32, trim_whitespace=True)
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField(max_length=254)
    governorate = serializers.ChoiceField(choices=Governorate.choices)
    city = serializers.CharField(max_length=100)
    address_line = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    password_confirm = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": ["كلمتا المرور غير متطابقتين."]})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class AdminSetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class MeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    roles = serializers.SerializerMethodField()
    is_super_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "governorate",
            "city",
            "address_line",
            "phone_verified",
            "is_staff",
            "roles",
            "is_super_admin",
            "date_joined",
        ]
        read_only_fields = fields

    phone_verified = serializers.SerializerMethodField()

    def get_phone_verified(self, user: User) -> bool:
        return user.phone_verified_at is not None

    def get_roles(self, user: User) -> list[str]:
        return user_roles(user)

    def get_is_super_admin(self, user: User) -> bool:
        return Role.SUPER_ADMIN in user_roles(user)


class ProfileUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    governorate = serializers.ChoiceField(choices=Governorate.choices, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line = serializers.CharField(max_length=255, required=False, allow_blank=True)


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
        fields = [
            "id",
            "phone",
            "display_name",
            "email",
            "governorate",
            "city",
            "is_active",
            "is_staff",
            "roles",
            "date_joined",
            "last_login",
        ]
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
    # Required for new accounts; optional when promoting an existing customer.
    password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default="", trim_whitespace=False
    )


class StaffUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=120, required=False)
    roles = RolesField(allow_empty=False, required=False)


class ActivationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
