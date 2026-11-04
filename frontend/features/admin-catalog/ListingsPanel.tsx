"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import {
  artworkKey,
  createListing,
  deleteListing,
  listingAction,
  listingsKey,
  listListings,
  priceListing,
  updateListing,
  type AdminListing,
} from "./api";

const input = "min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3";
const OPEN = new Set(["draft", "active", "sold_out"]);
type Mode = "unique" | "limited" | "unlimited";
type Status = "draft" | "active" | "sold_out" | "ended" | "withdrawn";
type Problem = "pricing_not_approved" | "artwork_not_public" | "no_stock" | "window_ended";

/** "2026-11-04T10:00:00Z" ⇄ value of <input type="datetime-local"> (local time). */
const toLocalInput = (iso: string | null | undefined) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
};
const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);

function fieldError(error: unknown): string | null {
  return error ? errorText(error) : null;
}

function CreateListing({ artworkId, onDone }: { artworkId: string; onDone: () => void }) {
  const t = useTranslations("admin.listings");
  const [mode, setMode] = useState<Mode>("unique");
  const [total, setTotal] = useState("2");
  const [maxPerOrder, setMaxPerOrder] = useState("1");
  const create = useMutation({
    mutationFn: () =>
      createListing(artworkId, {
        quantity_mode: mode,
        quantity_total: mode === "limited" ? Number(total) : null,
        max_per_order: mode === "unique" ? 1 : Number(maxPerOrder),
      }),
    onSuccess: onDone,
  });
  return (
    <div className="flex flex-col gap-4">
      {create.error ? <Alert tone="error">{errorText(create.error)}</Alert> : null}
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {t("quantityMode")}
          <select className={input} value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            {(["unique", "limited", "unlimited"] as const).map((m) => (
              <option key={m} value={m}>
                {t(`modes.${m}`)}
              </option>
            ))}
          </select>
        </label>
        {mode === "limited" ? (
          <label className="flex flex-col gap-1 text-sm">
            {t("quantityTotal")}
            <input className={`${input} w-28`} inputMode="numeric" dir="ltr" value={total} onChange={(e) => setTotal(e.target.value)} />
          </label>
        ) : null}
        {mode !== "unique" ? (
          <label className="flex flex-col gap-1 text-sm">
            {t("maxPerOrder")}
            <input className={`${input} w-28`} inputMode="numeric" dir="ltr" value={maxPerOrder} onChange={(e) => setMaxPerOrder(e.target.value)} />
          </label>
        ) : null}
        <Button loading={create.isPending} onClick={() => create.mutate()}>
          {t("create")}
        </Button>
      </div>
    </div>
  );
}

function PricingForm({ listing, onSaved }: { listing: AdminListing; onSaved: (l: AdminListing) => void }) {
  const t = useTranslations("admin.listings");
  const [price, setPrice] = useState(listing.price_usd ?? "");
  const [commission, setCommission] = useState(listing.commission_rate_override ?? "");
  const [depositType, setDepositType] = useState<string>(listing.deposit_type ?? "");
  const [depositValue, setDepositValue] = useState(listing.deposit_value ?? "");
  const save = useMutation({
    mutationFn: () =>
      priceListing(listing.id, {
        price_usd: price,
        commission_rate_override: commission === "" ? null : commission,
        deposit_type: depositType,
        deposit_value: depositType ? depositValue : null,
      }),
    onSuccess: onSaved,
  });
  const inherited = listing.effective_deposit;
  return (
    <fieldset className="flex flex-col gap-4 rounded-[var(--radius-control)] bg-surface/50 p-4">
      <legend className="text-sm font-medium text-primary">{t("pricing")}</legend>
      {save.error ? <Alert tone="error">{fieldError(save.error)}</Alert> : null}
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {t("price")}
          <input className={`${input} w-32`} inputMode="decimal" dir="ltr" value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("commission")}
          <input className={`${input} w-24`} inputMode="decimal" dir="ltr" value={commission} onChange={(e) => setCommission(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("depositType")}
          <select className={input} value={depositType} onChange={(e) => setDepositType(e.target.value)}>
            <option value="">
              {t("depositDefault", {
                value: inherited.type === "fixed" ? formatUsd(inherited.value) : `${Number(inherited.value)}%`,
              })}
            </option>
            <option value="fixed">{t("depositFixed")}</option>
            <option value="percentage">{t("depositPercentage")}</option>
          </select>
        </label>
        {depositType ? (
          <label className="flex flex-col gap-1 text-sm">
            {t("depositValue")}
            <input className={`${input} w-28`} inputMode="decimal" dir="ltr" value={depositValue} onChange={(e) => setDepositValue(e.target.value)} />
          </label>
        ) : null}
        <Button loading={save.isPending} disabled={!price} onClick={() => save.mutate()}>
          {t("approvePricing")}
        </Button>
      </div>
      <p className="text-xs text-muted">{t("commissionHint", { rate: Number(listing.effective_commission_rate) })}</p>
    </fieldset>
  );
}

function StockForm({ listing, onSaved }: { listing: AdminListing; onSaved: (l: AdminListing) => void }) {
  const t = useTranslations("admin.listings");
  const [total, setTotal] = useState(String(listing.quantity_total ?? ""));
  const [maxPerOrder, setMaxPerOrder] = useState(String(listing.max_per_order));
  const [startsAt, setStartsAt] = useState(toLocalInput(listing.starts_at));
  const [endsAt, setEndsAt] = useState(toLocalInput(listing.ends_at));
  const save = useMutation({
    mutationFn: () =>
      updateListing(listing.id, {
        ...(listing.quantity_mode === "limited" ? { quantity_total: Number(total) } : {}),
        ...(listing.quantity_mode !== "unique" ? { max_per_order: Number(maxPerOrder) } : {}),
        starts_at: fromLocalInput(startsAt),
        ends_at: fromLocalInput(endsAt),
      }),
    onSuccess: onSaved,
  });
  return (
    <div className="flex flex-col gap-3">
      {save.error ? <Alert tone="error">{errorText(save.error)}</Alert> : null}
      <div className="flex flex-wrap items-end gap-4">
        {listing.quantity_mode === "limited" ? (
          <label className="flex flex-col gap-1 text-sm">
            {t("quantityTotal")}
            <input className={`${input} w-24`} inputMode="numeric" dir="ltr" value={total} onChange={(e) => setTotal(e.target.value)} />
          </label>
        ) : null}
        {listing.quantity_mode !== "unique" ? (
          <label className="flex flex-col gap-1 text-sm">
            {t("maxPerOrder")}
            <input className={`${input} w-24`} inputMode="numeric" dir="ltr" value={maxPerOrder} onChange={(e) => setMaxPerOrder(e.target.value)} />
          </label>
        ) : null}
        <label className="flex flex-col gap-1 text-sm">
          {t("startsAt")}
          <input type="datetime-local" className={input} dir="ltr" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("endsAt")}
          <input type="datetime-local" className={input} dir="ltr" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
        </label>
        <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>
          {t("save")}
        </Button>
      </div>
    </div>
  );
}

function CurrentListing({ listing, artworkId }: { listing: AdminListing; artworkId: string }) {
  const t = useTranslations("admin.listings");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const { data: me } = useCurrentUser();
  const [reason, setReason] = useState("");
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: listingsKey(artworkId) });
    void queryClient.invalidateQueries({ queryKey: artworkKey(artworkId) });
  };
  const action = useMutation({
    mutationFn: (name: "activate" | "withdraw") => listingAction(listing.id, name, name === "withdraw" ? { reason } : undefined),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: () => deleteListing(listing.id), onSuccess: refresh });
  const status = listing.status as Status;
  const problems = (listing.activation_problems ?? []) as Problem[];
  const stock =
    listing.quantity_mode === "unlimited"
      ? t("stockUnlimited", { reserved: listing.quantity_reserved, sold: listing.quantity_sold })
      : t("stock", { available: listing.quantity_available, reserved: listing.quantity_reserved, sold: listing.quantity_sold });
  const deposit =
    listing.effective_deposit.type === "fixed"
      ? formatUsd(listing.effective_deposit.value)
      : `${Number(listing.effective_deposit.value)}%`;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          <span className="font-medium">{t(`status.${status}`)}</span> · {t(`modes.${listing.quantity_mode as Mode}`)}
          {listing.price_usd ? (
            <>
              {" "}
              · <bdi dir="ltr">{formatUsd(listing.price_usd)}</bdi>
            </>
          ) : null}
        </p>
        <span className={`text-xs ${listing.purchasable ? "text-olive" : "text-muted"}`}>
          {listing.purchasable ? t("purchasable") : t("notPurchasable")}
        </span>
      </div>
      <p className="text-sm text-muted">{stock}</p>
      <p className="text-sm text-muted">
        {listing.pricing_approved_at
          ? t("pricingApproved", { name: listing.pricing_approved_by ?? "—", date: formatDateTime(listing.pricing_approved_at) })
          : t("pricingPending")}
        {listing.pricing_approved_at ? ` · ${t("effective", { rate: Number(listing.effective_commission_rate), deposit })}` : null}
      </p>
      {problems.length ? (
        <ul className="list-inside list-disc text-sm text-primary">
          {problems.map((p) => (
            <li key={p}>{t(`problems.${p}`)}</li>
          ))}
        </ul>
      ) : null}
      {action.error ?? remove.error ? <Alert tone="error">{errorText(action.error ?? remove.error)}</Alert> : null}

      {me?.is_super_admin ? <PricingForm key={listing.updated_at} listing={listing} onSaved={refresh} /> : null}
      <StockForm key={`stock-${listing.updated_at}`} listing={listing} onSaved={refresh} />

      <div className="flex flex-wrap items-end gap-3 border-t border-border/60 pt-4">
        {status === "draft" ? (
          <Button disabled={problems.length > 0} loading={action.isPending} onClick={() => action.mutate("activate")}>
            {t("activate")}
          </Button>
        ) : null}
        {status === "draft" && !listing.activated_at ? (
          <Button
            variant="ghost"
            loading={remove.isPending}
            onClick={() => {
              if (window.confirm(tc("confirmDelete"))) remove.mutate();
            }}
          >
            {t("deleteDraft")}
          </Button>
        ) : null}
        {status !== "draft" ? (
          <>
            <label className="flex flex-col gap-1 text-sm">
              {t("withdrawReason")}
              <input className={input} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            <Button variant="secondary" loading={action.isPending} onClick={() => action.mutate("withdraw")}>
              {t("withdraw")}
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}

export function ListingsPanel({ artworkId }: { artworkId: string }) {
  const t = useTranslations("admin.listings");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const listings = useQuery({ queryKey: listingsKey(artworkId), queryFn: () => listListings(artworkId) });
  const current = listings.data?.find((l) => OPEN.has(l.status));
  const history = listings.data?.filter((l) => l !== current) ?? [];

  return (
    <section aria-labelledby="artwork-listing" className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-border/60 p-6">
      <h2 id="artwork-listing" className="text-lg font-medium text-primary">
        {t("title")}
      </h2>
      <p className="text-xs text-muted">{t("intro")}</p>
      {listings.isPending ? <p className="text-sm text-muted">{tc("loading")}</p> : null}
      {listings.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {listings.data && !current ? (
        <>
          <p className="text-sm text-muted">{t("none")}</p>
          <CreateListing artworkId={artworkId} onDone={() => void queryClient.invalidateQueries({ queryKey: listingsKey(artworkId) })} />
        </>
      ) : null}
      {current ? <CurrentListing listing={current} artworkId={artworkId} /> : null}
      {history.length ? (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted">{t("history")}</summary>
          <ul className="mt-2 flex flex-col gap-1">
            {history.map((l) => (
              <li key={l.id} className="text-muted">
                {t(`status.${l.status as Status}`)} · {l.price_usd ? formatUsd(l.price_usd) : "—"} ·{" "}
                {formatDateTime(l.closed_at ?? l.created_at)}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
