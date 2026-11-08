"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { orderTone, StatusBadge } from "@/components/ui/StatusBadge";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import {
  adminOrderKey,
  cancelOrder,
  completeOrder,
  confirmPayment,
  customDeposit,
  getAdminOrder,
  recordPayment,
  removeItem,
  saveDelivery,
  saveNotes,
  voidPayment,
  type AdminOrder,
} from "./api";

const input =
  "min-h-11 w-full rounded-[var(--radius-control)] border border-border bg-white px-3";
const card =
  "rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-5";
const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}${Math.random()}`;

function Section({
  id,
  title,
  children,
  aside,
}: {
  id: string;
  title: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={card}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="text-base font-medium text-primary">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Every staff action returns the full order: one cache entry, always the server's truth. */
function useOrderAction<V>(
  number: string,
  fn: (v: V) => Promise<AdminOrder>,
  onDone?: () => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (order) => {
      queryClient.setQueryData(adminOrderKey(number), order);
      void queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
      onDone?.();
    },
  });
}

function Items({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const [removing, setRemoving] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const remove = useOrderAction(
    order.number,
    (id: string) => removeItem(order.number, id, reason),
    () => {
      setRemoving(null);
      setReason("");
    },
  );
  return (
    <Section id="adm-items" title={t("items")}>
      <ul className="divide-y divide-border/60">
        {order.items.map((item) => (
          <li
            key={item.id}
            className={`flex flex-col gap-2 py-3 ${item.status === "removed" ? "opacity-50" : ""}`}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="font-medium">
                {item.title}
                {item.quantity > 1 ? (
                  <span className="text-muted tabular-nums">
                    {" "}
                    × {item.quantity}
                  </span>
                ) : null}
              </span>
              <bdi
                dir="ltr"
                className={
                  item.status === "removed" ? "line-through" : "font-medium"
                }
              >
                {formatUsd(item.line_total)}
              </bdi>
            </div>
            <p className="text-xs text-muted">
              {t("commission", {
                rate: Number(item.commission_rate_snapshot),
                amount: formatUsd(item.commission_amount_snapshot),
                payee: formatUsd(item.payee_amount_snapshot),
              })}
            </p>
            {item.status === "removed" ? (
              <p className="text-xs text-primary">
                {t("removed", { reason: item.removed_reason })}
              </p>
            ) : null}
            {order.actions.remove_items && item.status === "active" ? (
              removing === item.id ? (
                <div className="flex flex-wrap items-end gap-2">
                  <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs">
                    {t("removeReason")}
                    <input
                      className={input}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      autoFocus
                    />
                  </label>
                  <Button
                    variant="secondary"
                    disabled={!reason.trim()}
                    loading={remove.isPending}
                    onClick={() => remove.mutate(item.id)}
                  >
                    {t("removeItem")}
                  </Button>
                  <Button variant="ghost" onClick={() => setRemoving(null)}>
                    ✕
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  className="self-start text-xs text-muted underline-offset-4 hover:text-primary hover:underline"
                  onClick={() => setRemoving(item.id)}
                >
                  {t("removeItem")}
                </button>
              )
            ) : null}
          </li>
        ))}
      </ul>
      {remove.error ? (
        <p className="mt-2 text-sm text-primary">{errorText(remove.error)}</p>
      ) : null}
    </Section>
  );
}

function PaymentForm({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const beforeDeposit = order.status === "pending_deposit";
  // Refund mode only when a refund is due; otherwise only money towards the order.
  const finished = order.actions.record_refund;
  const [kind, setKind] = useState(
    finished ? "refund" : beforeDeposit ? "deposit" : "payment",
  );
  const [amount, setAmount] = useState(
    finished
      ? order.amount_paid
      : beforeDeposit
        ? order.deposit_due
        : order.remaining,
  );
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [confirmNow, setConfirmNow] = useState(true);
  const [key, setKey] = useState(newKey);
  const record = useOrderAction(
    order.number,
    () =>
      recordPayment(
        order.number,
        { kind, amount, method, reference, notes, confirm: confirmNow },
        key,
      ),
    () => {
      setKey(newKey()); // the next payment is a new operation
      setReference("");
      setNotes("");
    },
  );
  const fieldErrors =
    record.error instanceof ApiError ? record.error.fieldErrors : {};
  return (
    <form
      className="mt-4 grid gap-4 border-t border-border/60 pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        record.mutate(undefined);
      }}
    >
      <h3 className="text-sm font-medium">{t("recordPayment")}</h3>
      {record.error && !Object.keys(fieldErrors).length ? (
        <Alert tone="error">{errorText(record.error)}</Alert>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("kind")}
          <select
            className={input}
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {(finished
              ? (["refund"] as const)
              : beforeDeposit
                ? (["deposit", "payment"] as const)
                : (["payment"] as const)
            ).map((k) => (
              <option key={k} value={k}>
                {t(`kinds.${k}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("amount")}
          <input
            className={input}
            inputMode="decimal"
            dir="ltr"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          {fieldErrors.amount ? (
            <span className="text-xs text-primary">
              {fieldErrors.amount.join(" ")}
            </span>
          ) : null}
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("method")}
          <select
            className={input}
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            {(
              ["cash", "bank_transfer", "money_transfer", "other"] as const
            ).map((m) => (
              <option key={m} value={m}>
                {t(`methods.${m}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {beforeDeposit ? (
        <div className="flex flex-wrap gap-2 text-xs">
          <button
            type="button"
            className="rounded-full border border-border px-3 py-1 hover:border-secondary"
            onClick={() => {
              setKind("deposit");
              setAmount(order.deposit_due);
            }}
          >
            {t("suggestDeposit", { amount: formatUsd(order.deposit_due) })}
          </button>
          <button
            type="button"
            className="rounded-full border border-border px-3 py-1 hover:border-secondary"
            onClick={() => {
              setKind("payment");
              setAmount(order.remaining);
            }}
          >
            {t("suggestRest", { amount: formatUsd(order.remaining) })}
          </button>
        </div>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          {t("reference")}
          <input
            className={input}
            dir="auto"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("paymentNotes")}
          <input
            className={input}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-[var(--color-primary)]"
          checked={confirmNow}
          onChange={(e) => setConfirmNow(e.target.checked)}
        />
        {t("confirmNow")}
      </label>
      <div>
        <Button type="submit" loading={record.isPending} disabled={!amount}>
          {t("recordPayment")}
        </Button>
      </div>
    </form>
  );
}

function Payments({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const [voiding, setVoiding] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const confirm = useOrderAction(order.number, (id: string) =>
    confirmPayment(order.number, id),
  );
  const voidIt = useOrderAction(
    order.number,
    (id: string) => voidPayment(order.number, id, reason),
    () => setVoiding(null),
  );
  const error = confirm.error ?? voidIt.error;
  return (
    <Section id="adm-payments" title={t("payments")}>
      {order.payments.length === 0 ? (
        <p className="text-sm text-muted">{t("noPayments")}</p>
      ) : null}
      <ul className="flex flex-col gap-3">
        {order.payments.map((p) => (
          <li
            key={p.id}
            className={`rounded-[var(--radius-control)] border border-border/50 p-3 text-sm ${p.status === "voided" ? "opacity-50" : ""}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">
                {t(`kinds.${p.kind as "deposit"}`)} ·{" "}
                <bdi dir="ltr">{formatUsd(p.amount)}</bdi> ·{" "}
                {t(`methods.${p.method as "cash"}`)}
              </span>
              <StatusBadge
                tone={
                  p.status === "confirmed"
                    ? "success"
                    : p.status === "voided"
                      ? "closed"
                      : "action"
                }
              >
                {t(`paymentStatus.${p.status as "recorded"}`)}
              </StatusBadge>
            </div>
            <p className="mt-1 text-xs text-muted">
              {formatDateTime(p.created_at)} ·{" "}
              {t("recordedBy", { name: p.recorded_by })}
              {p.confirmed_by
                ? ` · ${t("confirmedBy", { name: p.confirmed_by })}`
                : ""}
              {p.reference ? ` · ${p.reference}` : ""}
              {p.void_reason ? ` · ${p.void_reason}` : ""}
            </p>
            {p.status === "recorded" ? (
              voiding === p.id ? (
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs">
                    {t("voidReason")}
                    <input
                      className={input}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      autoFocus
                    />
                  </label>
                  <Button
                    variant="secondary"
                    disabled={!reason.trim()}
                    loading={voidIt.isPending}
                    onClick={() => voidIt.mutate(p.id)}
                  >
                    {t("void")}
                  </Button>
                </div>
              ) : (
                <div className="mt-2 flex gap-2">
                  <Button
                    loading={confirm.isPending}
                    onClick={() => confirm.mutate(p.id)}
                  >
                    {t("confirm")}
                  </Button>
                  <Button variant="ghost" onClick={() => setVoiding(p.id)}>
                    {t("void")}
                  </Button>
                </div>
              )
            ) : null}
          </li>
        ))}
      </ul>
      {error ? (
        <p className="mt-2 text-sm text-primary">{errorText(error)}</p>
      ) : null}
      {order.actions.record_payment || order.actions.record_refund ? (
        <PaymentForm
          key={`${order.payments.length}-${order.status}`}
          order={order}
        />
      ) : null}
    </Section>
  );
}

function DeliveryForm({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const to = useTranslations("orders");
  const d = order.delivery;
  const [method, setMethod] = useState(d.method);
  const [carrier, setCarrier] = useState(d.carrier_name);
  const [status, setStatus] = useState(d.status);
  const [notes, setNotes] = useState(d.notes);
  const save = useOrderAction(order.number, () =>
    saveDelivery(order.number, {
      method,
      carrier_name: carrier,
      status,
      notes,
    }),
  );
  return (
    <Section id="adm-delivery" title={t("delivery")}>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("deliveryMethod")}
          <select
            className={input}
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            {(["", "pickup", "courier", "platform", "other"] as const).map(
              (m) => (
                <option key={m} value={m}>
                  {t(`methodsDelivery.${m}`)}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("carrier")}
          <input
            className={input}
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("deliveryStatus")}
          <select
            className={input}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {(["not_started", "in_transit", "delivered"] as const).map((s) => (
              <option key={s} value={s}>
                {to(`deliveryStatus.${s}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="mt-4 flex flex-col gap-1 text-sm">
        {t("deliveryNotes")}
        <input
          className={input}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      {d.delivered_at ? (
        <p className="mt-2 text-xs text-olive">
          {t("deliveredAt")}: {formatDateTime(d.delivered_at)}
        </p>
      ) : null}
      {save.error ? (
        <p className="mt-2 text-sm text-primary">{errorText(save.error)}</p>
      ) : null}
      <div className="mt-4">
        <Button
          variant="secondary"
          loading={save.isPending}
          onClick={() => save.mutate(undefined)}
        >
          {t("saveDelivery")}
        </Button>
      </div>
    </Section>
  );
}

function ActionsPanel({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const tc = useTranslations("common");
  const [dialog, setDialog] = useState<"platform" | "customer" | null>(null);
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState(order.deposit_due);
  const [depositReason, setDepositReason] = useState("");
  const cancel = useOrderAction(
    order.number,
    (kind: "platform" | "customer") => cancelOrder(order.number, kind, reason),
    () => {
      setDialog(null);
      setReason("");
    },
  );
  const complete = useOrderAction(order.number, () =>
    completeOrder(order.number),
  );
  const deposit = useOrderAction(order.number, () =>
    customDeposit(order.number, amount, depositReason),
  );
  const a = order.actions;
  const any =
    a.complete ||
    a.custom_deposit ||
    a.cancel_by_platform ||
    a.cancel_for_customer;
  if (!any) return null;
  return (
    <Section id="adm-actions" title={tc("actions")}>
      <div className="flex flex-col gap-4">
        {complete.error ? (
          <Alert tone="error">{errorText(complete.error)}</Alert>
        ) : null}
        {order.status === "confirmed" ? (
          <div>
            <Button
              className="w-full"
              disabled={!a.complete}
              loading={complete.isPending}
              onClick={() => complete.mutate(undefined)}
            >
              {t("complete")}
            </Button>
            {!a.complete ? (
              <p className="mt-1 text-xs text-muted">{t("completeHint")}</p>
            ) : null}
          </div>
        ) : null}
        {a.custom_deposit ? (
          <details className="text-sm">
            <summary className="cursor-pointer text-primary">
              {t("customDeposit")}
            </summary>
            <p className="mt-2 text-xs text-muted">{t("customDepositHint")}</p>
            <div className="mt-3 flex flex-col gap-2">
              <label className="flex flex-col gap-1">
                {t("customAmount")}
                <input
                  className={input}
                  inputMode="decimal"
                  dir="ltr"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1">
                {t("reason")}
                <input
                  className={input}
                  value={depositReason}
                  onChange={(e) => setDepositReason(e.target.value)}
                />
              </label>
              {deposit.error ? (
                <p className="text-primary">{errorText(deposit.error)}</p>
              ) : null}
              <Button
                variant="secondary"
                disabled={!depositReason.trim()}
                loading={deposit.isPending}
                onClick={() => deposit.mutate(undefined)}
              >
                {tc("save")}
              </Button>
            </div>
          </details>
        ) : null}
        {a.cancel_for_customer ? (
          <div>
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => setDialog("customer")}
            >
              {t("cancelCustomer")}
            </Button>
            <p className="mt-1 text-xs text-muted">{t("cancelCustomerHint")}</p>
          </div>
        ) : null}
        {a.cancel_by_platform ? (
          <div>
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => setDialog("platform")}
            >
              {t("cancelPlatform")}
            </Button>
            <p className="mt-1 text-xs text-muted">{t("cancelPlatformHint")}</p>
          </div>
        ) : null}
      </div>
      <ConfirmDialog
        open={dialog !== null}
        title={
          dialog === "customer" ? t("cancelCustomer") : t("cancelPlatform")
        }
        confirmLabel={
          dialog === "customer" ? t("cancelCustomer") : t("cancelPlatform")
        }
        cancelLabel={tc("cancel")}
        busy={cancel.isPending}
        onConfirm={() => dialog && reason.trim() && cancel.mutate(dialog)}
        onCancel={() => setDialog(null)}
      >
        <p>
          {dialog === "customer"
            ? t("cancelCustomerHint")
            : t("cancelPlatformHint")}
        </p>
        <label className="mt-4 flex flex-col gap-1 text-sm text-text">
          {t("cancelReason")}
          <textarea
            className="min-h-20 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        {cancel.error ? (
          <p className="mt-2 text-sm text-primary">{errorText(cancel.error)}</p>
        ) : null}
      </ConfirmDialog>
    </Section>
  );
}

function Notes({ order }: { order: AdminOrder }) {
  const t = useTranslations("admin.orders");
  const [value, setValue] = useState(order.internal_notes);
  const save = useOrderAction(order.number, () =>
    saveNotes(order.number, value),
  );
  return (
    <Section id="adm-notes" title={t("internalNotes")}>
      <textarea
        className="min-h-24 w-full rounded-[var(--radius-control)] border border-border bg-white px-3 py-2 text-sm"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <div className="mt-2 flex items-center gap-3">
        <Button
          variant="secondary"
          disabled={value === order.internal_notes}
          loading={save.isPending}
          onClick={() => save.mutate(undefined)}
        >
          {t("saveNotes")}
        </Button>
        {save.isSuccess && value === order.internal_notes ? (
          <span className="text-xs text-olive">{t("saved")}</span>
        ) : null}
      </div>
    </Section>
  );
}

export function OrderManager({ number }: { number: string }) {
  const t = useTranslations("admin.orders");
  const ts = useTranslations("status_order");
  const to = useTranslations("orders");
  const tg = useTranslations("governorates");
  const tc = useTranslations("common");
  const order = useQuery({
    queryKey: adminOrderKey(number),
    queryFn: () => getAdminOrder(number),
  });
  if (order.isPending)
    return (
      <div
        className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60"
        aria-busy
      />
    );
  if (order.isError)
    return (
      <Alert tone="error">
        {order.error instanceof ApiError && order.error.status === 404
          ? to("notFound")
          : tc("loadError")}
      </Alert>
    );
  const o = order.data;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary" dir="ltr">
            {o.number}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {formatDateTime(o.created_at)} ·{" "}
            {t("policy", {
              version: o.policy_version,
              date: formatDateTime(o.policy_accepted_at),
            })}
          </p>
        </div>
        <StatusBadge tone={orderTone(o.status)}>
          {ts(o.status as "expired")}
        </StatusBadge>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Items order={o} />
          <Payments order={o} />
          {o.actions.delivery ? (
            <DeliveryForm key={o.delivery.status} order={o} />
          ) : null}
        </div>
        <div className="flex flex-col gap-6">
          <Section id="adm-money" title={to("summary")}>
            <dl className="flex flex-col gap-2 text-sm">
              {(
                [
                  [to("subtotal"), o.subtotal],
                  [
                    `${to("deposit")} (${t(`depositStatus.${o.deposit_status as "pending"}`)})`,
                    o.deposit_due,
                  ],
                  [to("paid"), o.amount_paid],
                  [to("remaining"), o.remaining],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-muted">{label}</dt>
                  <dd>
                    <bdi dir="ltr">{formatUsd(value)}</bdi>
                  </dd>
                </div>
              ))}
            </dl>
            {o.status === "pending_deposit" ? (
              <p className="mt-3 text-xs text-primary">
                {to("expiresAt", {
                  date: formatDateTime(o.reservation_expires_at),
                })}
              </p>
            ) : null}
          </Section>
          <ActionsPanel order={o} />
          <Section id="adm-contact" title={t("contact")}>
            <p className="text-sm leading-7">
              {o.contact_name}
              <br />
              <bdi dir="ltr">{o.contact_phone}</bdi>
              {o.contact_email ? (
                <>
                  <br />
                  <bdi dir="ltr">{o.contact_email}</bdi>
                </>
              ) : null}
              <br />
              {[
                o.governorate ? tg(o.governorate as "damascus") : "",
                o.city,
                o.address_line,
              ]
                .filter(Boolean)
                .join("، ")}
            </p>
            {o.customer_notes ? (
              <p className="mt-3 rounded bg-surface/50 p-3 text-sm">
                {o.customer_notes}
              </p>
            ) : null}
          </Section>
          <Section id="adm-history" title={t("history")}>
            <ol className="flex flex-col gap-3 border-s border-border ps-4 text-sm">
              {o.history.map((h, i) => (
                <li key={i}>
                  <p className="font-medium">{ts(h.to_status as "expired")}</p>
                  <p className="text-xs text-muted">
                    {formatDateTime(h.created_at)} · {h.actor ?? t("system")}
                    {h.reason ? ` · ${h.reason}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          </Section>
          <Notes order={o} />
        </div>
      </div>
    </div>
  );
}
