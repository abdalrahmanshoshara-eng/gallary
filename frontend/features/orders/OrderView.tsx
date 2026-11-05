"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { splitDuration, useCountdown } from "@/components/ui/Countdown";
import { Icon } from "@/components/ui/Icon";
import { orderTone, StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import { cancelOrder, getOrder, orderKey, ordersKey, type Order } from "./api";

type Status = keyof typeof STEP_OF;
const STEP_OF = {
  pending_deposit: 1,
  deposit_confirmed: 2,
  payment_pending: 2,
  confirmed: 3,
  completed: 4,
  expired: -1,
  cancelled_by_customer: -1,
  cancelled_by_platform: -1,
} as const;
const STEPS = ["placed", "deposit", "payment", "delivery"] as const;

function Countdown({ order, onElapsed }: { order: Order; onElapsed: () => void }) {
  const t = useTranslations("orders");
  const left = useCountdown(order.reservation_expires_at, order.server_now, onElapsed);
  const { hours, minutes, seconds } = splitDuration(left);
  const urgent = left < 2 * 3600 * 1000;
  return (
    <p className={`text-3xl font-semibold tabular-nums ${urgent ? "text-primary" : "text-text"}`} dir="rtl" role="timer" aria-live="off">
      {hours > 0 ? t("countdown", { hours, minutes }) : t("countdownShort", { minutes, seconds })}
    </p>
  );
}

function Progress({ status }: { status: Status }) {
  const t = useTranslations("orders");
  const current = STEP_OF[status];
  if (current < 0) return null;
  return (
    <ol aria-label={t("progress")} className="grid grid-cols-4 gap-2">
      {STEPS.map((step, index) => {
        const done = index < current || status === "completed";
        const active = index === current && status !== "completed";
        return (
          <li key={step} className="flex flex-col gap-2" aria-current={active ? "step" : undefined}>
            <span className={`h-1.5 rounded-full ${done ? "bg-olive" : active ? "bg-secondary" : "bg-surface"}`} />
            <span className={`text-xs ${done || active ? "text-text" : "text-muted"}`}>{t(`steps.${step}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function OrderView({ number, justCreated }: { number: string; justCreated: boolean }) {
  const t = useTranslations("orders");
  const ts = useTranslations("status_order");
  const tg = useTranslations("governorates");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const order = useQuery({ queryKey: orderKey(number), queryFn: () => getOrder(number) });
  const cancel = useMutation({
    mutationFn: () => cancelOrder(number, reason),
    onSuccess: (updated) => {
      queryClient.setQueryData(orderKey(number), updated);
      void queryClient.invalidateQueries({ queryKey: ordersKey });
      setConfirming(false);
    },
  });

  if (order.isPending) return <div className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (order.isError) {
    const missing = order.error instanceof ApiError && order.error.status === 404;
    return (
      <Alert tone="error">
        {missing ? t("notFound") : tc("loadError")}{" "}
        <Link href="/orders" className="underline">
          {t("allOrders")}
        </Link>
      </Alert>
    );
  }
  const o = order.data;
  const status = o.status as Status;
  const pending = status === "pending_deposit";

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary md:text-3xl">{t("number", { number: o.number })}</h1>
          <p className="mt-1 text-sm text-muted">{t("placedOn", { date: formatDateTime(o.created_at) })}</p>
        </div>
        <StatusBadge tone={orderTone(status)}>{ts(status)}</StatusBadge>
      </header>

      {justCreated && pending ? <Alert tone="success">{t("created")}</Alert> : null}
      {o.source === "auction" && pending ? (
        <Alert tone="info">
          <span className="font-medium">{t("auctionOrder")}</span> — {t("auctionDeadlineHint")}
        </Alert>
      ) : null}
      {cancel.isSuccess ? <Alert tone="success">{t("cancelled")}</Alert> : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-8">
          {pending ? (
            <section aria-labelledby="next-step" className="rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-6">
              <div className="flex flex-wrap items-end justify-between gap-6">
                <div>
                  <h2 id="next-step" className="flex items-center gap-2 text-sm text-muted">
                    <Icon name="clock" className="size-4" />
                    {t("deadlineTitle")}
                  </h2>
                  <Countdown order={o} onElapsed={() => void order.refetch()} />
                  <p className="mt-1 text-xs text-muted">{t("expiresAt", { date: formatDateTime(o.reservation_expires_at) })}</p>
                </div>
                <div className="text-end">
                  <p className="text-sm text-muted">{t("depositTitle")}</p>
                  <bdi dir="ltr" className="text-2xl font-semibold text-primary">
                    {formatUsd(o.deposit_due)}
                  </bdi>
                </div>
              </div>
              <div className="mt-6">
                {o.whatsapp_url ? (
                  <>
                    <a
                      href={o.whatsapp_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-12 w-full items-center justify-center rounded-[var(--radius-control)] bg-primary px-6 font-medium text-on-primary hover:bg-primary/90 sm:w-auto"
                    >
                      {t("payViaWhatsapp")}
                    </a>
                    <p className="mt-2 text-xs text-muted">{t("whatsappHint")}</p>
                  </>
                ) : (
                  <p className="text-sm">{t("noWhatsapp")}</p>
                )}
              </div>
              {o.can_cancel ? (
                <div className="mt-6 border-t border-border/60 pt-4">
                  <button type="button" className="text-sm text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setConfirming(true)}>
                    {t("cancel")}
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}

          {status === "expired" ? <Alert tone="info">{o.source === "auction" ? t("auctionExpiredBody") : t("expiredBody")}</Alert> : null}
          {status.startsWith("cancelled") ? (
            <Alert tone="info">
              {t("cancelledBody")}
              {o.cancelled_reason ? ` — ${o.cancelled_reason}` : ""}
            </Alert>
          ) : null}
          {status === "deposit_confirmed" || status === "payment_pending" ? <Alert tone="info">{t("afterDepositContact")}</Alert> : null}

          <Progress status={status} />

          <section aria-labelledby="order-items">
            <h2 id="order-items" className="mb-2 text-lg font-medium text-primary">
              {t("items", { count: o.items.length })}
            </h2>
            <ul className="divide-y divide-border/60 border-y border-border/60">
              {o.items.map((item) => (
                <li key={item.id} className="flex items-center gap-4 py-4">
                  <div className="size-20 shrink-0 overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-2">
                    {item.image ? <ResponsiveImage image={item.image.image} alt={item.title} sizes="5rem" /> : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <Link href={`/artworks/${item.artwork_slug}`} className="font-medium text-primary hover:text-secondary">
                      {item.title}
                    </Link>
                    <p className="text-sm text-muted tabular-nums">
                      {item.quantity} × <bdi dir="ltr">{formatUsd(item.unit_price)}</bdi>
                    </p>
                  </div>
                  <bdi dir="ltr" className="font-medium">
                    {formatUsd(item.line_total)}
                  </bdi>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <aside className="flex flex-col gap-6">
          <section aria-labelledby="order-summary" className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-6">
            <h2 id="order-summary" className="text-lg font-medium text-primary">
              {t("summary")}
            </h2>
            <dl className="mt-4 flex flex-col gap-3 text-sm">
              {(
                [
                  ["subtotal", o.subtotal],
                  ["deposit", o.deposit_due],
                  ["paid", o.amount_paid],
                  ["remaining", o.remaining],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-muted">{t(label)}</dt>
                  <dd>
                    <bdi dir="ltr" className={label === "remaining" ? "font-semibold text-primary" : ""}>
                      {formatUsd(value)}
                    </bdi>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section aria-labelledby="order-delivery" className="rounded-[var(--radius-card)] border border-border/60 p-6 text-sm">
            <h2 id="order-delivery" className="font-medium text-primary">
              {t("deliveryTo")}
            </h2>
            <p className="mt-2 leading-7">
              {o.contact_name}
              <br />
              {[o.governorate ? tg(o.governorate as "damascus") : "", o.city].filter(Boolean).join("، ")}
              <br />
              {o.address_line}
            </p>
            {o.delivery && status !== "pending_deposit" && !status.startsWith("cancelled") && status !== "expired" ? (
              <p className="mt-3 text-muted">{t(`deliveryStatus.${o.delivery.status as "not_started"}`)}</p>
            ) : null}
            {o.customer_notes ? (
              <>
                <h3 className="mt-4 font-medium text-primary">{t("notes")}</h3>
                <p className="mt-1 whitespace-pre-line text-muted">{o.customer_notes}</p>
              </>
            ) : null}
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={confirming}
        title={t("cancelTitle", { number: o.number })}
        confirmLabel={t("cancelConfirm")}
        cancelLabel={t("keep")}
        busy={cancel.isPending}
        onConfirm={() => cancel.mutate()}
        onCancel={() => setConfirming(false)}
      >
        <p>{t("cancelBody")}</p>
        <label className="mt-4 flex flex-col gap-1 text-sm text-text">
          {t("cancelReason")}
          <input className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        {cancel.error ? <p className="mt-3 text-sm text-primary">{errorText(cancel.error)}</p> : null}
      </ConfirmDialog>
    </div>
  );
}
