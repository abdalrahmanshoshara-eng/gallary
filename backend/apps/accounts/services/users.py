"""
Profile updates and staff administration (PRD §6, BR-907).

Only a Super Admin creates staff accounts and assigns roles. Guards: nobody can change
their own staff status/roles or deactivate themselves, and the last Super Admin cannot be
removed. Every administrative change is audited in the same transaction.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q

from apps.audit import services as audit
from apps.core.errors import ConflictError

from ..errors import LastSuperAdminError, SelfModificationError
from ..models import SessionRevokeReason, User
from ..phone import normalize_phone
from ..roles import ROLE_NAMES, Role, user_roles
from .sessions import revoke_user_sessions


class EmailInUseError(ConflictError):
    code = "EMAIL_IN_USE"
    message = "هذا البريد الإلكتروني مستخدم في حساب آخر."


class AlreadyStaffError(ConflictError):
    code = "ALREADY_STAFF"
    message = "هذا الرقم مرتبط بحساب موظف بالفعل."


def update_profile(user: User, *, display_name: str | None = None, email: str | None = None) -> User:
    fields = []
    if display_name is not None:
        user.display_name = display_name.strip()
        fields.append("display_name")
    if email is not None:
        normalized = User.objects.normalize_email(email.strip()) or None
        if normalized and User.objects.filter(email__iexact=normalized).exclude(pk=user.pk).exists():
            raise EmailInUseError()
        user.email = normalized
        fields.append("email")
    if fields:
        user.save(update_fields=fields)
    return user


def _validate_roles(roles: Iterable[str]) -> list[str]:
    cleaned = sorted(set(roles))
    unknown = [r for r in cleaned if r not in ROLE_NAMES]
    if unknown:
        raise ConflictError("دور غير معروف.", code="UNKNOWN_ROLE", details={"roles": unknown})
    if not cleaned:
        raise ConflictError("يجب اختيار دور واحد على الأقل.", code="ROLE_REQUIRED")
    return cleaned


def _set_roles(user: User, roles: list[str]) -> None:
    groups = {g.name: g for g in Group.objects.filter(name__in=ROLE_NAMES)}
    keep = user.groups.exclude(name__in=ROLE_NAMES)
    user.groups.set([*keep, *(groups[r] for r in roles)])


def _super_admin_count(exclude: User | None = None) -> int:
    qs = User.objects.filter(is_active=True, is_staff=True).filter(
        Q(is_superuser=True) | Q(groups__name=Role.SUPER_ADMIN)
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.distinct().count()


def _guard_super_admin_removal(target: User, new_roles: list[str] | None, deactivating: bool) -> None:
    was_super = Role.SUPER_ADMIN in user_roles(target)
    loses_super = deactivating or (new_roles is not None and Role.SUPER_ADMIN not in new_roles)
    if was_super and loses_super and _super_admin_count(exclude=target) == 0:
        raise LastSuperAdminError()


@transaction.atomic
def create_staff(*, actor: User, raw_phone: str, display_name: str, roles: Iterable[str], ip: str | None) -> User:
    phone = normalize_phone(raw_phone)
    roles = _validate_roles(roles)
    user = User.objects.select_for_update().filter(phone=phone).first()
    if user is not None and user.is_staff:
        raise AlreadyStaffError()
    promoted = user is not None
    if user is None:
        if not display_name.strip():
            raise ConflictError("اسم الموظف مطلوب.", code="NAME_REQUIRED", http_status=400)
        user = User.objects.create_user(phone=phone, display_name=display_name.strip(), is_staff=True)
    else:
        if user.pk == actor.pk:
            raise SelfModificationError()
        user.is_staff = True
        if display_name.strip():
            user.display_name = display_name.strip()
        user.save(update_fields=["is_staff", "display_name"])
        # Existing customer sessions run under the customer policy; force a fresh login.
        revoke_user_sessions(user, SessionRevokeReason.ROLE_CHANGED)
    _set_roles(user, roles)
    audit.record(
        actor=actor,
        action="staff.created" if not promoted else "staff.promoted",
        entity=user,
        changes={"roles": roles, "display_name": user.display_name},
        ip=ip,
    )
    return user


@transaction.atomic
def update_staff(
    *, actor: User, target: User, display_name: str | None, roles: Iterable[str] | None, ip: str | None
) -> User:
    if not target.is_staff:
        raise ConflictError("هذا الحساب ليس حساب موظف.", code="NOT_STAFF")
    changes: dict[str, object] = {}
    new_roles = None
    if roles is not None:
        new_roles = _validate_roles(roles)
        if target.pk == actor.pk:
            raise SelfModificationError()
        _guard_super_admin_removal(target, new_roles, deactivating=False)
        before = user_roles(target)
        if before != new_roles:
            _set_roles(target, new_roles)
            changes["roles"] = {"from": before, "to": new_roles}
    if display_name is not None and display_name.strip() != target.display_name:
        changes["display_name"] = {"from": target.display_name, "to": display_name.strip()}
        target.display_name = display_name.strip()
        target.save(update_fields=["display_name"])
    if changes:
        audit.record(actor=actor, action="staff.updated", entity=target, changes=changes, ip=ip)
    return target


@transaction.atomic
def revoke_staff_access(*, actor: User, target: User, ip: str | None) -> User:
    if target.pk == actor.pk:
        raise SelfModificationError()
    if not target.is_staff:
        raise ConflictError("هذا الحساب ليس حساب موظف.", code="NOT_STAFF")
    _guard_super_admin_removal(target, [], deactivating=False)
    before = user_roles(target)
    target.is_staff = False
    target.is_superuser = False
    target.save(update_fields=["is_staff", "is_superuser"])
    target.groups.remove(*Group.objects.filter(name__in=ROLE_NAMES))
    revoke_user_sessions(target, SessionRevokeReason.ROLE_CHANGED)
    audit.record(actor=actor, action="staff.access_revoked", entity=target, changes={"roles": before}, ip=ip)
    return target


@transaction.atomic
def set_user_active(*, actor: User, target: User, active: bool, reason: str, ip: str | None) -> User:
    if target.pk == actor.pk:
        raise SelfModificationError()
    if target.is_active == active:
        return target
    if not active:
        _guard_super_admin_removal(target, None, deactivating=True)
    target.is_active = active
    target.save(update_fields=["is_active"])
    if not active:
        revoke_user_sessions(target, SessionRevokeReason.DEACTIVATED)
    audit.record(
        actor=actor,
        action="user.activated" if active else "user.deactivated",
        entity=target,
        reason=reason,
        ip=ip,
    )
    return target


@transaction.atomic
def admin_revoke_sessions(*, actor: User, target: User, ip: str | None) -> int:
    count = revoke_user_sessions(target, SessionRevokeReason.ADMIN)
    audit.record(actor=actor, action="user.sessions_revoked", entity=target, changes={"count": count}, ip=ip)
    return count


@transaction.atomic
def bootstrap_super_admin(*, raw_phone: str, display_name: str) -> tuple[User, bool]:
    """Create or promote the first Super Admin (management command; no actor)."""
    phone = normalize_phone(raw_phone)
    user = User.objects.select_for_update().filter(phone=phone).first()
    created = user is None
    if created:
        user = User.objects.create_user(phone=phone, display_name=display_name, is_staff=True)
    else:
        user.is_staff = True
        user.is_active = True
        if display_name:
            user.display_name = display_name
        user.save(update_fields=["is_staff", "is_active", "display_name"])
        revoke_user_sessions(user, SessionRevokeReason.ROLE_CHANGED)
    user.groups.add(Group.objects.get(name=Role.SUPER_ADMIN))
    audit.record(actor=None, action="staff.bootstrap_super_admin", entity=user, changes={"created": created})
    return user, created
