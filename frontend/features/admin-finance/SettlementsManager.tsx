"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge, type Tone } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { pageCount } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import {
  cancelSettlement,
  getSettlementSummary,
  holdSettlement,
  listPayeesDue,
  listSettlements,
  newKey,
  paySettlements,
  releaseSettlement,
  settlementsKey,
  sumAmounts,
  type PayeeDue,
  type Settlement,
} from "./api";

const FILTERS = ["pending", "on_hold", "paid", "cancelled", "all"] as const;
type Filter = (typeof FILTERS)[number];
const TONE: Record<string, Tone> = { pending: "action", on_hold: "progress", paid: "success", cancelled: "closed" };
const field = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";
const dateOnly = (iso: string) => new Intl.DateTimeFormat("ar-SY-u-nu-latn", { dateStyle: "long", timeZone: "UTC" }).format(new Date(iso));
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Damascus" }).format(new Date());

function Summary() {
  const t = useTranslations("admin.settlements.summary");
  const summary = useQuery({ queryKey: [...settlementsKey, "summary"], queryFn: getSettlementSummary });
  const cards = [
    ["pending", summary.data?.pending],
    ["on_hold", summary.data?.on_hold],
    ["paid_this_month", summary.data?.paid_this_month],
  ] as const;
  return (
    <dl className="grid gap-4 sm:grid-cols-3">
      {cards.map(([key, total]) => (
        <div key={key} className={`rounded-[var(--radius-card)] border p-4 ${key === "pending" ? "border-secondary/60 bg-white/70" : "border-border/60"}`}>
          <dt className="text-sm text-muted">{t(key)}</dt>
          <dd className="mt-1">
            {total ? (
              <>
                <span className="block text-2xl font-semibold text-primary tabular-nums">
                  <bdi dir="ltr">{formatUsd(total.amount)}</bdi>
                </span>
                <span className="text-xs text-muted">{t("items", { count: total.count })}</span>
              </>
            ) : (
              <span className="block h-8 w-24 animate-pulse rounded bg-surface/70" aria-hidden />
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function PayeesDue({ onPick }: { onPick: (p: PayeeDue) => void }) {
  const t = useTranslations("admin.settlements");
  const payees = useQuery({ queryKey: [...settlementsKey, "payees"], queryFn: listPayeesDue });
  if (!payees.data?.length) return null;
  return (
    <section aria-labelledby="payees-due" className="rounded-[var(--radius-card)] border border-border/60 p-4">
      <h2 id="payees-due" className="text-base font-medium text-primary">
        {t("byPayee")}
      </h2>
      <p className="mb-3 text-xs text-muted">{t("byPayeeHint")}</p>
      <ul className="divide-y divide-border/50">
        {payees.data.map((p) => (
          <li key={p.payee_key} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <span className="min-w-0">
              <span className="font-medium text-text">{p.payee_name}</span>{" "}
              <span className="text-xs text-muted">
                {t(`payeeTypes.${p.payee_type as "artist"}`)} · {t("summary.items", { count: p.count })}
              </span>
            </span>
            <span className="flex items-center gap-3">
              <bdi dir="ltr" className="font-semibold tabular-nums text-primary">
                {formatUsd(p.amount)}
              </bdi>
              <Button variant="secondary" className="min-h-9 px-4" onClick={() => onPick(p)}>
                {t("showPayee")}
              </Button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

type Dialog = { kind: "pay" } | { kind: "hold" | "cancel"; row: Settlement } | null;

/**
 * Settlements desk (BR-704…706): what is owed, grouped by payee; one transfer per payee is
 * recorded with its reference. Only the actions the server allows for each row are shown.
 */
export function SettlementsManager() {
  const t = useTranslations("admin.settlements");
  const ts = useTranslations("admin.settlements.status");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("pending");
  const [payee, setPayee] = useState<PayeeDue | null>(null);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Map<string, Settlement>>(new Map());
  const [dialog, setDialog] = useState<Dialog>(null);
  const [reason, setReason] = useState("");
  const [payForm, setPayForm] = useState({ reference: "", paid_at: today(), notes: "", key: "" });
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = { status: filter, search: debounced, payee: payee?.payee_key ?? "", page };
  const rows = useQuery({
    queryKey: [...settlementsKey, "list", params],
    queryFn: () => listSettlements(params),
    placeholderData: keepPreviousData,
  });

  const reset = (message: string) => {
    void queryClient.invalidateQueries({ queryKey: settlementsKey });
    void queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
    setDialog(null);
    setReason("");
    setSelected(new Map());
    setNotice(message);
  };
  const pay = useMutation({
    mutationFn: () =>
      paySettlements(
        { settlements: [...selected.keys()], reference: payForm.reference.trim(), paid_at: payForm.paid_at, notes: payForm.notes },
        payForm.key,
      ),
    onSuccess: () => {
      reset(t("paid"));
      setPayForm({ reference: "", paid_at: today(), notes: "", key: "" });
    },
  });
  const act = useMutation({
    mutationFn: ({ kind, row }: { kind: "hold" | "cancel" | "release"; row: Settlement }) =>
      kind === "hold" ? holdSettlement(row.id, reason) : kind === "cancel" ? cancelSettlement(row.id, reason) : releaseSettlement(row.id),
    onSuccess: (_, vars) => reset(t(vars.kind === "hold" ? "held" : vars.kind === "cancel" ? "cancelled" : "released")),
  });

  const selectedRows = [...selected.values()];
  const selectedPayee = selectedRows[0]?.payee_key ?? null;
  const selectedTotal = sumAmounts(selectedRows.map((r) => r.payee_amount));
  const totalPages = rows.data ? pageCount(rows.data.count) : 1;
  const pendingVisible = rows.data?.results.filter((r) => r.actions.includes("pay")) ?? [];
  const toggle = (row: Settlement) =>
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(row.id)) next.delete(row.id);
      else next.set(row.id, row);
      return next;
    });
  const changeFilter = (f: Filter) => {
    setFilter(f);
    setPage(1);
    setSelected(new Map());
    if (f !== "pending") setPayee(null);
  };

  return (
    <div className="flex flex-col gap-8">
      <Summary />
      {notice ? <Alert tone="success">{notice}</Alert> : null}
      {act.error && !dialog ? <Alert tone="error">{errorText(act.error)}</Alert> : null}

      {filter === "pending" && !payee ? (
        <PayeesDue
          onPick={(p) => {
            setPayee(p);
            setPage(1);
            setSelected(new Map());
          }}
        />
      ) : null}

      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {tc("search")}
          <input
            type="search"
            className={field}
            placeholder={t("search")}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <div role="tablist" aria-label={tc("status")} className="flex gap-2 overflow-x-auto pb-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filter === f}
              onClick={() => changeFilter(f)}
              className={`rounded-full border px-4 py-1.5 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                filter === f ? "border-primary bg-primary text-on-primary" : "border-border hover:border-secondary"
              }`}
            >
              {t(`filters.${f}`)}
            </button>
          ))}
        </div>
        {payee ? (
          <p className="flex flex-wrap items-center gap-3 text-sm">
            <span className="rounded-full bg-secondary/15 px-3 py-1 text-primary">{t("payeeFilter", { name: payee.payee_name })}</span>
            <button type="button" className="text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setPayee(null)}>
              {t("allPayees")}
            </button>
          </p>
        ) : null}
      </div>

      {rows.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {rows.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {rows.data && rows.data.results.length === 0 ? (
        <p className="py-10 text-center text-muted">{filter === "pending" && !debounced ? t("emptyPending") : t("empty")}</p>
      ) : null}

      {rows.data && rows.data.results.length > 0 ? (
        <div className="flex flex-col gap-2">
          {payee && pendingVisible.length > 1 ? (
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-[var(--color-primary)]"
                checked={pendingVisible.every((r) => selected.has(r.id))}
                onChange={(e) => setSelected(e.target.checked ? new Map(pendingVisible.map((r) => [r.id, r])) : new Map())}
              />
              {t("selectAll")}
            </label>
          ) : null}
          <ul className="divide-y divide-border/60 border-y border-border/60" aria-busy={rows.isFetching || undefined}>
            {rows.data.results.map((row) => {
              const payable = row.actions.includes("pay");
              const otherPayee = selectedPayee !== null && selectedPayee !== row.payee_key;
              return (
                <li key={row.id} className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 py-4 md:grid-cols-[auto_minmax(0,1.4fr)_minmax(0,1fr)_9rem_10rem]">
                  <span className="pt-1">
                    {payable ? (
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--color-primary)] disabled:opacity-40"
                        checked={selected.has(row.id)}
                        disabled={otherPayee}
                        title={otherPayee ? t("mixedPayees") : undefined}
                        aria-label={t("selectRow", { artwork: row.artwork_title })}
                        onChange={() => toggle(row)}
                      />
                    ) : (
                      <span className="inline-block size-4" aria-hidden />
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-primary">{row.artwork_title}</span>
                    <Link href={`/admin/orders/${row.order_number}`} className="text-xs text-muted hover:text-primary" dir="ltr">
                      {row.order_number}
                    </Link>
                    <span className="block text-xs text-muted">{formatDateTime(row.created_at)}</span>
                  </span>
                  <span className="col-start-2 min-w-0 text-sm md:col-start-auto">
                    <span className="block truncate">{row.payee_name}</span>
                    <span className="text-xs text-muted">{t(`payeeTypes.${row.payee_type as "artist"}`)}</span>
                  </span>
                  <span className="col-start-2 text-sm md:col-start-auto">
                    <span className="block font-semibold tabular-nums text-primary">
                      <bdi dir="ltr">{formatUsd(row.payee_amount)}</bdi>
                    </span>
                    <span className="block text-xs text-muted">
                      {t("columns.gross")} {formatUsd(row.gross_amount)} · {t("columns.commission")} {formatUsd(row.platform_commission)} (
                      {t("rate", { rate: Number(row.commission_rate) })})
                    </span>
                  </span>
                  <span className="col-start-2 flex flex-col items-start gap-2 md:col-start-auto">
                    <StatusBadge tone={TONE[row.status] ?? "progress"}>{ts(row.status)}</StatusBadge>
                    {row.status === "paid" && row.paid_at ? (
                      <span className="text-xs text-muted">
                        {t("paidInfo", { date: dateOnly(row.paid_at), reference: row.reference })}
                        {row.paid_by ? ` · ${t("paidBy", { name: row.paid_by })}` : ""}
                      </span>
                    ) : null}
                    {row.status_reason ? <span className="text-xs text-muted">{row.status_reason}</span> : null}
                    {row.order_cancelled_after_payment ? <span className="text-xs font-medium text-primary">{t("cancelledAfterPayment")}</span> : null}
                    <span className="flex flex-wrap gap-2">
                      {row.actions.includes("release") ? (
                        <button type="button" className="text-xs text-primary underline-offset-4 hover:underline" onClick={() => act.mutate({ kind: "release", row })}>
                          {t("release")}
                        </button>
                      ) : null}
                      {row.actions.includes("hold") ? (
                        <button type="button" className="text-xs text-primary underline-offset-4 hover:underline" onClick={() => setDialog({ kind: "hold", row })}>
                          {t("hold")}
                        </button>
                      ) : null}
                      {row.actions.includes("cancel") ? (
                        <button type="button" className="text-xs text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setDialog({ kind: "cancel", row })}>
                          {t("cancel")}
                        </button>
                      ) : null}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {totalPages > 1 ? (
        <div className="flex items-center gap-4 text-sm">
          <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {tc("previous")}
          </Button>
          <span>{tc("pageOf", { page, total: totalPages })}</span>
          <Button variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            {tc("next")}
          </Button>
        </div>
      ) : null}

      {selected.size > 0 ? (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-secondary/60 bg-white p-4 shadow-lg">
          <p className="text-sm">{t("selection", { count: selected.size, amount: formatUsd(selectedTotal) })}</p>
          <Button
            onClick={() => {
              // A fresh key per payment attempt; retries inside the dialog reuse it (no double record).
              setPayForm((f) => ({ ...f, key: newKey() }));
              pay.reset();
              setDialog({ kind: "pay" });
            }}
          >
            {t("pay")}
          </Button>
        </div>
      ) : null}

      <ConfirmDialog
        open={dialog?.kind === "pay"}
        title={t("payTitle", { name: selectedRows[0]?.payee_name ?? "" })}
        confirmLabel={t("payConfirm")}
        cancelLabel={t("back")}
        busy={pay.isPending}
        confirmDisabled={!payForm.reference.trim() || !payForm.paid_at}
        onCancel={() => setDialog(null)}
        onConfirm={() => pay.mutate()}
      >
        <p className="font-medium text-text">{t("payBody", { count: selected.size, amount: formatUsd(selectedTotal) })}</p>
        {pay.error ? (
          <div className="mt-3">
            <Alert tone="error">{errorText(pay.error)}</Alert>
          </div>
        ) : null}
        <div className="mt-4 flex flex-col gap-3 text-text">
          <label className="flex flex-col gap-1 text-sm">
            {t("reference")}
            <input className={field} dir="ltr" value={payForm.reference} onChange={(e) => setPayForm({ ...payForm, reference: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {t("paidAt")}
            <input type="date" className={field} dir="ltr" max={today()} value={payForm.paid_at} onChange={(e) => setPayForm({ ...payForm, paid_at: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {t("notes")}
            <input className={field} value={payForm.notes} onChange={(e) => setPayForm({ ...payForm, notes: e.target.value })} />
          </label>
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog?.kind === "hold" || dialog?.kind === "cancel"}
        title={dialog && dialog.kind !== "pay" ? t(dialog.kind === "hold" ? "holdTitle" : "cancelTitle", { artwork: dialog.row.artwork_title }) : ""}
        confirmLabel={dialog?.kind === "cancel" ? t("cancel") : t("hold")}
        cancelLabel={t("back")}
        busy={act.isPending}
        confirmDisabled={!reason.trim()}
        onCancel={() => {
          setDialog(null);
          setReason("");
        }}
        onConfirm={() => dialog && dialog.kind !== "pay" && act.mutate({ kind: dialog.kind, row: dialog.row })}
      >
        {dialog?.kind === "cancel" ? <p>{t("cancelBody")}</p> : null}
        {act.error ? (
          <div className="mt-3">
            <Alert tone="error">{errorText(act.error)}</Alert>
          </div>
        ) : null}
        <label className="mt-3 flex flex-col gap-1 text-sm text-text">
          {dialog?.kind === "cancel" ? t("cancelReason") : t("holdReason")}
          <textarea className="min-h-20 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2" value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
      </ConfirmDialog>
    </div>
  );
}
