"""BR-704 for orders confirmed before settlements existed: one settlement per active item."""

from django.db import migrations


def backfill(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")
    Settlement = apps.get_model("settlements", "Settlement")
    items = OrderItem.objects.filter(
        order__status__in=["confirmed", "completed"], status="active", settlement__isnull=True
    ).select_related("artwork__artist", "artwork__owner_user", "order")
    for item in items:
        artwork = item.artwork
        payee = {"payee_type": "artist"}
        if item.payee_type_snapshot == "owner" and artwork.owner_user_id:
            owner = artwork.owner_user
            payee.update(payee_type="owner", owner_user=owner, payee_name=owner.display_name or artwork.owner_name or owner.phone, payee_key=f"owner:{owner.pk}")
        elif artwork.artist_id:
            payee.update(artist=artwork.artist, payee_name=artwork.artist.name, payee_key=f"artist:{artwork.artist_id}")
        else:
            payee.update(payee_name=artwork.creator_name_override, payee_key=f"name:{artwork.creator_name_override}"[:40])
        Settlement.objects.create(
            order_item=item,
            gross_amount=item.line_total,
            commission_rate=item.commission_rate_snapshot,
            platform_commission=item.commission_amount_snapshot,
            payee_amount=item.payee_amount_snapshot,
            created_at=item.order.confirmed_at or item.order.created_at,
            **payee,
        )


class Migration(migrations.Migration):
    dependencies = [("settlements", "0001_initial"), ("orders", "0001_initial")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
