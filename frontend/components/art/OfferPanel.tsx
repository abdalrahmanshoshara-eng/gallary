import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { BuyBox } from "@/features/cart/BuyBox";
import type { Offer } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

/**
 * Price and availability on the artwork page, with the buy action (BuyBox) when the offer
 * can be bought now; otherwise the reason it cannot.
 */
export async function OfferPanel({ offer, archived }: { offer: Offer | null | undefined; archived: boolean }) {
  const t = await getTranslations("catalog");
  if (archived) return <p className="text-olive">{t("archivedNotice")}</p>;
  if (!offer) return <p className="text-muted">{t("notForSale")}</p>;

  const reason = offer.unavailable_reason as
    | "sold_out"
    | "reserved"
    | "not_started"
    | "ended"
    | "artwork_unavailable"
    | "not_active"
    | null;
  const stock =
    offer.quantity_mode === "unique"
      ? t("offer.unique")
      : offer.available === null
        ? t("offer.unlimited")
        : t("offer.available", { count: offer.available });

  return (
    <div className="flex flex-col gap-3">
      {offer.price_usd ? (
        <p className="flex items-baseline gap-3">
          <span className="text-sm text-muted">{t("offer.price")}</span>
          <bdi dir="ltr" className={`text-2xl font-semibold ${reason === "sold_out" ? "text-muted line-through" : "text-primary"}`}>
            {formatUsd(offer.price_usd)}
          </bdi>
        </p>
      ) : null}
      {offer.purchasable ? (
        <>
          <p className="text-sm text-olive">{stock}</p>
          {offer.max_per_order > 1 ? <p className="text-xs text-muted">{t("offer.maxPerOrder", { count: offer.max_per_order })}</p> : null}
          {offer.ends_at ? <p className="text-xs text-muted">{t("offer.endsAt", { date: formatDateTime(offer.ends_at) })}</p> : null}
          <div className="mt-2">
            {/* Suspense: BuyBox reads the URL (?add=) while the page itself stays cacheable. */}
            <Suspense fallback={<div className="h-11" aria-hidden />}>
              <BuyBox offer={offer} />
            </Suspense>
          </div>
          <p className="text-xs text-muted">{t("offer.depositNote")}</p>
        </>
      ) : (
        <p className="font-medium text-primary">
          {reason === "not_started" && offer.starts_at
            ? t("offer.startsAt", { date: formatDateTime(offer.starts_at) })
            : t(`offer.status.${reason ?? "not_active"}`)}
        </p>
      )}
    </div>
  );
}
