"use client";

import { useTranslations } from "next-intl";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { QuantityStepper } from "@/components/ui/QuantityStepper";
import { Link } from "@/i18n/navigation";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import { acceptPrices, removeLine, updateLine, useCart, useCartMutation, type Cart, type CartLine } from "./api";

type Problem =
  | "sold_out"
  | "reserved"
  | "not_started"
  | "ended"
  | "artwork_unavailable"
  | "not_active"
  | "quantity_limit"
  | "insufficient_stock"
  | "auction_only";

const continueClass =
  "inline-flex min-h-12 w-full items-center justify-center rounded-[var(--radius-control)] bg-primary px-6 font-medium text-on-primary transition-colors duration-300 ease-calm hover:bg-primary/90";

function Line({ line }: { line: CartLine }) {
  const t = useTranslations("cart");
  const tb = useTranslations("buy");
  const update = useCartMutation(updateLine);
  const remove = useCartMutation(removeLine);
  const busy = update.isPending || remove.isPending;
  const unavailable = Boolean(line.problem);

  return (
    <li className={`flex gap-4 py-6 ${busy ? "opacity-60" : ""}`} aria-busy={busy || undefined}>
      <Link href={`/artworks/${line.artwork_slug}`} className="size-24 shrink-0 overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-2 sm:size-28">
        {line.image ? <ResponsiveImage image={line.image.image} alt={line.title} sizes="7rem" /> : null}
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link href={`/artworks/${line.artwork_slug}`} className="font-heading text-lg text-primary hover:text-secondary">
              {line.title}
            </Link>
            <p className="text-sm text-muted">{line.creator_name}</p>
          </div>
          <button
            type="button"
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-primary"
            aria-label={`${t("remove")}: ${line.title}`}
            disabled={busy}
            onClick={() => remove.mutate({ id: line.id })}
          >
            <Icon name="trash" />
          </button>
        </div>
        {unavailable ? (
          <p className="text-sm font-medium text-primary">{t(`problem.${line.problem as Problem}`)}</p>
        ) : (
          <>
            {line.price_changed && line.unit_price ? (
              <p className="text-sm text-secondary">
                {t("priceChanged", { from: formatUsd(line.price_at_add), to: formatUsd(line.unit_price) })}
              </p>
            ) : null}
            <div className="mt-auto flex flex-wrap items-center justify-between gap-3">
              {line.max_quantity > 1 ? (
                <QuantityStepper
                  value={line.quantity}
                  max={line.max_quantity}
                  onChange={(quantity) => update.mutate({ id: line.id, quantity })}
                  label={tb("quantity")}
                  decreaseLabel={tb("decrease")}
                  increaseLabel={tb("increase")}
                  disabled={busy}
                />
              ) : (
                <span className="text-xs text-muted">{line.unit_price ? t("unitPrice", { price: formatUsd(line.unit_price) }) : null}</span>
              )}
              <bdi dir="ltr" className="font-medium text-primary">
                {formatUsd(line.line_total)}
              </bdi>
            </div>
          </>
        )}
        {update.error ?? remove.error ? <p className="text-sm text-primary">{errorText(update.error ?? remove.error)}</p> : null}
      </div>
    </li>
  );
}

function Summary({ cart, compact = false }: { cart: Cart; compact?: boolean }) {
  const t = useTranslations("cart");
  const action = cart.can_checkout ? (
    <Link href="/checkout" className={continueClass}>
      {t("continue")}
    </Link>
  ) : (
    <button type="button" disabled className={`${continueClass} cursor-not-allowed opacity-50`}>
      {t("continue")}
    </button>
  );
  if (compact) {
    return (
      <div className="flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted">{t("subtotal")}</p>
          <bdi dir="ltr" className="text-lg font-semibold text-primary">
            {formatUsd(cart.subtotal)}
          </bdi>
        </div>
        <div className="w-1/2">{action}</div>
      </div>
    );
  }
  return (
    <section aria-labelledby="cart-summary" className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-6">
      <h2 id="cart-summary" className="text-lg font-medium text-primary">
        {t("summary")}
      </h2>
      <dl className="mt-4 flex flex-col gap-3 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{t("subtotal")}</dt>
          <dd><bdi dir="ltr" className="font-semibold text-primary">{formatUsd(cart.subtotal)}</bdi></dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{t("depositNow")}</dt>
          <dd><bdi dir="ltr">{formatUsd(cart.deposit_due)}</bdi></dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{t("rest")}</dt>
          <dd><bdi dir="ltr">{formatUsd(cart.remaining_after_deposit)}</bdi></dd>
        </div>
      </dl>
      <div className="mt-6">{action}</div>
      <p className="mt-3 text-xs text-muted">{t("noReservation")}</p>
    </section>
  );
}

export function CartView() {
  const t = useTranslations("cart");
  const tc = useTranslations("common");
  const cart = useCart();
  const accept = useCartMutation(acceptPrices);

  if (cart.isPending) {
    return (
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]" aria-busy>
        <div className="flex flex-col gap-6">
          {[0, 1].map((i) => (
            <div key={i} className="flex gap-4">
              <div className="size-28 animate-pulse rounded-[var(--radius-card)] bg-surface" />
              <div className="flex flex-1 flex-col gap-3 pt-2">
                <div className="h-4 w-2/3 animate-pulse rounded bg-surface" />
                <div className="h-3 w-1/3 animate-pulse rounded bg-surface" />
              </div>
            </div>
          ))}
        </div>
        <div className="h-56 animate-pulse rounded-[var(--radius-card)] bg-surface/70" />
      </div>
    );
  }
  if (cart.isError) {
    return (
      <Alert tone="error">
        {tc("loadError")}{" "}
        <button type="button" className="underline" onClick={() => cart.refetch()}>
          {tc("retry")}
        </button>
      </Alert>
    );
  }
  const data = cart.data;
  if (data.count === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <Icon name="bag" className="size-12 text-secondary" />
        <p className="text-lg text-primary">{t("empty")}</p>
        <p className="max-w-sm text-sm text-muted">{t("emptyHint")}</p>
        <Link href="/artworks" className="mt-2 rounded-[var(--radius-control)] bg-primary px-6 py-3 text-on-primary">
          {t("browse")}
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="grid gap-10 pb-28 lg:grid-cols-[minmax(0,1fr)_22rem] lg:pb-0">
        <div>
          <p className="text-sm text-muted">{t("itemsCount", { count: data.count })}</p>
          <div className="mt-4 flex flex-col gap-3">
            {data.blocking.includes("price_changed") ? (
              <Alert tone="info">
                <span>{t("pricesNotice")}</span>{" "}
                <Button variant="secondary" className="mt-3" loading={accept.isPending} onClick={() => accept.mutate(undefined)}>
                  {t("acceptPrices")}
                </Button>
              </Alert>
            ) : null}
            {data.blocking.includes("unavailable") ? <Alert tone="error">{t("unavailableNotice")}</Alert> : null}
          </div>
          <ul className="divide-y divide-border/60 border-b border-border/60">
            {data.lines.map((line) => (
              <Line key={line.id} line={line} />
            ))}
          </ul>
        </div>
        <div className="hidden lg:block">
          <div className="sticky top-24">
            <Summary cart={data} />
          </div>
        </div>
      </div>
      {/* Phones: the total and the next step stay within thumb reach. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/95 px-4 py-3 backdrop-blur lg:hidden">
        <Summary cart={data} compact />
      </div>
    </>
  );
}
