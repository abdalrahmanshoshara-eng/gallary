"use client";

import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { QuantityStepper } from "@/components/ui/QuantityStepper";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import type { Offer } from "@/lib/catalog/types";
import { errorText } from "@/lib/forms";

import { addToCart, useCart, useCartMutation, useIsCustomer } from "./api";

const primaryLink =
  "inline-flex min-h-11 items-center justify-center rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary transition-colors duration-300 ease-calm hover:bg-primary/90";
const secondaryLink =
  "inline-flex min-h-11 items-center justify-center rounded-[var(--radius-control)] border border-secondary px-6 text-sm font-medium text-primary hover:bg-surface";

export function maxQuantity(offer: Offer): number {
  if (offer.quantity_mode === "unique") return 1;
  if (offer.available === null) return offer.max_per_order;
  return Math.max(1, Math.min(offer.max_per_order, offer.available));
}

/**
 * The purchase action on an artwork page, adapted to who is looking:
 * visitor → sign in and come back (the piece is then added automatically);
 * staff → informational note; customer → add / already-in-cart with next step.
 */
export function BuyBox({ offer }: { offer: Offer }) {
  const t = useTranslations("buy");
  const { isCustomer, user, isPending } = useIsCustomer();
  const cart = useCart();
  const add = useCartMutation(addToCart);
  const [quantity, setQuantity] = useState(1);
  const [notice, setNotice] = useState<"added" | "addedAfterLogin" | null>(null);
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const intentHandled = useRef(false);
  const max = maxQuantity(offer);
  const line = cart.data?.lines.find((l) => l.listing === offer.id);

  // Returning from sign-in with ?add=<offer>&qty=n: add once, then clean the URL.
  useEffect(() => {
    if (intentHandled.current || !isCustomer || !cart.data || params.get("add") !== offer.id) return;
    intentHandled.current = true;
    const qty = Math.min(max, Math.max(1, Number(params.get("qty")) || 1));
    const done = () => router.replace(pathname, { scroll: false });
    if (line) return done();
    add.mutate({ listing: offer.id, quantity: qty }, { onSuccess: () => setNotice("addedAfterLogin"), onSettled: done });
  }, [isCustomer, cart.data, params, offer.id, max, line, add, router, pathname]);

  if (isPending) return <div className="h-11" aria-hidden />;

  if (!user) {
    const next = `${pathname}?add=${offer.id}&qty=${quantity}`;
    return (
      <div className="flex flex-col gap-3">
        {max > 1 ? (
          <QuantityStepper
            value={quantity}
            max={max}
            onChange={setQuantity}
            label={t("quantity")}
            decreaseLabel={t("decrease")}
            increaseLabel={t("increase")}
          />
        ) : null}
        <Link href={{ pathname: "/login", query: { next } }} className={primaryLink}>
          {t("loginToBuy")}
        </Link>
        <p className="text-xs text-muted">{t("loginHint")}</p>
      </div>
    );
  }

  if (!isCustomer) return <p className="text-sm text-muted">{t("staffNote")}</p>;

  if (line) {
    return (
      <div className="flex flex-col gap-3">
        {notice ? <Alert tone="success">{t(notice)}</Alert> : null}
        <p className="flex items-center gap-2 text-sm text-olive">
          <Icon name="check" className="size-4" />
          {t("inCart")}
          {line.quantity > 1 ? <span className="tabular-nums">× {line.quantity}</span> : null}
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/checkout" className={primaryLink}>
            {t("checkoutNow")}
          </Link>
          <Link href="/cart" className={secondaryLink}>
            {t("viewCart")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {add.error ? <Alert tone="error">{errorText(add.error)}</Alert> : null}
      <div className="flex flex-wrap items-center gap-3">
        {max > 1 ? (
          <QuantityStepper
            value={quantity}
            max={max}
            onChange={setQuantity}
            label={t("quantity")}
            decreaseLabel={t("decrease")}
            increaseLabel={t("increase")}
            disabled={add.isPending}
          />
        ) : null}
        <Button
          loading={add.isPending}
          disabled={cart.isPending}
          onClick={() => add.mutate({ listing: offer.id, quantity }, { onSuccess: () => setNotice("added") })}
        >
          <Icon name="bag" className="size-5" />
          {add.isPending ? t("adding") : t("addToCart")}
        </Button>
      </div>
    </div>
  );
}
