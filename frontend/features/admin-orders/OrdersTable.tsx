"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { orderTone, StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { pageCount } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { adminOrdersKey, listAdminOrders } from "./api";

const FILTERS = ["open", "pending_deposit", "deposit_confirmed", "payment_pending", "confirmed", "completed", "expired", "all"] as const;
type Filter = (typeof FILTERS)[number];

function timeLeft(deadline: string): { hours: number; minutes: number } {
  const ms = Math.max(0, Date.parse(deadline) - Date.now());
  return { hours: Math.floor(ms / 3_600_000), minutes: Math.floor((ms % 3_600_000) / 60_000) };
}

export function OrdersTable() {
  const t = useTranslations("admin.orders");
  const ts = useTranslations("status_order");
  const to = useTranslations("orders");
  const tc = useTranslations("common");
  const [filter, setFilter] = useState<Filter>("open");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [source, setSource] = useState<"all" | "cart" | "auction">("all");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const params = { status: filter, source, search: debounced, page };
  const orders = useQuery({
    queryKey: adminOrdersKey(params),
    queryFn: () => listAdminOrders(params),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000, // deadlines move; keep the queue honest
  });
  const totalPages = orders.data ? pageCount(orders.data.count) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          {tc("search")}
          <input
            type="search"
            className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
            placeholder={t("search")}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="flex max-w-xs flex-col gap-1 text-sm">
          {t("sourceLabel")}
          <select
            className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
            value={source}
            onChange={(e) => {
              setSource(e.target.value as typeof source);
              setPage(1);
            }}
          >
            {(["all", "cart", "auction"] as const).map((s) => (
              <option key={s} value={s}>
                {t(`filters.source.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <div role="tablist" aria-label={tc("status")} className="flex gap-2 overflow-x-auto pb-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filter === f}
              onClick={() => {
                setFilter(f);
                setPage(1);
              }}
              className={`rounded-full border px-4 py-1.5 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                filter === f ? "border-primary bg-primary text-on-primary" : "border-border hover:border-secondary"
              }`}
            >
              {t(`filters.${f}`)}
            </button>
          ))}
        </div>
      </div>

      {orders.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {orders.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {orders.data && orders.data.results.length === 0 ? <p className="py-10 text-center text-muted">{t("empty")}</p> : null}
      {orders.data && orders.data.results.length > 0 ? (
        <ul className="divide-y divide-border/60 border-y border-border/60" aria-busy={orders.isFetching || undefined}>
          {orders.data.results.map((order) => {
            const left = timeLeft(order.reservation_expires_at);
            return (
              <li key={order.number}>
                <Link
                  href={`/admin/orders/${order.number}`}
                  className="grid grid-cols-2 items-center gap-x-4 gap-y-2 py-4 hover:bg-surface/40 md:grid-cols-[10rem_minmax(0,1fr)_9rem_8rem_10rem]"
                >
                  <span className="flex flex-col">
                    <span className="font-medium text-primary" dir="ltr">
                      {order.number}
                    </span>
                    {order.source === "auction" ? <span className="text-xs text-secondary">{to("source.auction")}</span> : null}
                  </span>
                  <span className="min-w-0 truncate text-sm">
                    {order.customer} · <bdi dir="ltr" className="text-muted">{order.phone}</bdi>
                  </span>
                  <span>
                    <StatusBadge tone={orderTone(order.status)}>{ts(order.status as "expired")}</StatusBadge>
                  </span>
                  <span className="text-sm tabular-nums">
                    <bdi dir="ltr">{formatUsd(order.amount_paid)}</bdi> / <bdi dir="ltr">{formatUsd(order.subtotal)}</bdi>
                  </span>
                  <span className="text-xs text-muted">
                    {order.needs_action
                      ? t("expiresIn", { time: to("countdown", left) })
                      : t("createdAt", { date: formatDateTime(order.created_at) })}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
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
    </div>
  );
}
