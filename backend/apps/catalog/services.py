"""Classification management (BR-106/107)."""

from __future__ import annotations

from django.db import transaction

from apps.audit import services as audit
from apps.core.errors import ConflictError
from apps.core.slugs import unique_slug

from .models import Category, Term


class TermInUseError(ConflictError):
    code = "TERM_IN_USE"
    message = "لا يمكن حذف عنصر مستخدم في أعمال فنية. يمكنك تعطيله بدلاً من ذلك."


class InvalidParentError(ConflictError):
    code = "INVALID_PARENT"
    message = "التصنيفات على مستويين فقط: رئيسي وفرعي."


def _check_parent(category: Category | None, parent: Category | None) -> None:
    if parent is None:
        return
    if parent.parent_id is not None:
        raise InvalidParentError()
    is_existing = category is not None and category.pk is not None
    if is_existing and (parent.pk == category.pk or category.children.exists()):
        raise InvalidParentError()


@transaction.atomic
def create_term(model: type[Term], *, actor, data: dict) -> Term:
    if model is Category:
        _check_parent(None, data.get("parent"))
    slug = data.pop("slug", "") or unique_slug(model, data["name"])
    term = model.objects.create(slug=slug, **data)
    audit.record(actor=actor, action=f"{model._meta.model_name}.created", entity=term, changes={"name": term.name})
    return term


@transaction.atomic
def update_term(term: Term, *, actor, data: dict) -> Term:
    if isinstance(term, Category) and "parent" in data:
        _check_parent(term, data["parent"])
    changes = {}
    for field, value in data.items():
        old = getattr(term, field)
        if old != value:
            changes[field] = {
                "from": str(old) if old is not None else None,
                "to": str(value) if value is not None else None,
            }
            setattr(term, field, value)
    if changes:
        term.save()
        audit.record(actor=actor, action=f"{term._meta.model_name}.updated", entity=term, changes=changes)
    return term


def _in_use(term: Term) -> bool:
    if isinstance(term, Category):
        return term.artworks.exists() or term.children.exists()
    return term.artworks.exists()


@transaction.atomic
def delete_term(term: Term, *, actor) -> None:
    if _in_use(term):
        raise TermInUseError()
    audit.record(actor=actor, action=f"{term._meta.model_name}.deleted", entity=term, changes={"name": term.name})
    term.delete()
