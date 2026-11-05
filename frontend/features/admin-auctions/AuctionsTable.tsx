"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatusBadge, type Tone } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { pageCount } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { adminAuctionsKey, listAdminAuctions } from "./api";

const FILTERS = ["active", "draft", "scheduled", "live", "pending_winner_payment", "awarded", "ended", "cancelled", "all"] as const;
type Filter = (typeof FILTERS)[number];

export const AUCTION_TONE: Record<string, Tone> = {
  draft: "progress",
  scheduled: "progress",
  live: "action",
  pending_winner_payment: "action",
  awarded: "success",
  ended: "closed",
  cancelled: "closed",
};

export function AuctionsTable() {
  const t = useTranslations("admin.auctions");
  const ts = useTranslations("status_auction");
  const tc = useTranslations("common");
  const [filter, setFilter] = useState<Filter>("active");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const params = { status: filter, search: debounced, page };
  const auctions = useQuery({
    queryKey: adminAuctionsKey(params),
    queryFn: () => listAdminAuctions(params),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000,
  });
  const totalPages = auctions.data ? pageCount(auctions.data.count) : 1;

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

      {auctions.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {auctions.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {auctions.data && auctions.data.results.length === 0 ? <p className="py-10 text-center text-muted">{t("empty")}</p> : null}
      {auctions.data && auctions.data.results.length > 0 ? (
        <ul className="divide-y divide-border/60 border-y border-border/60" aria-busy={auctions.isFetching || undefined}>
          {auctions.data.results.map((a) => (
            <li key={a.id}>
              <Link
                href={`/admin/auctions/${a.id}`}
                className="grid grid-cols-2 items-center gap-x-4 gap-y-2 py-4 hover:bg-surface/40 md:grid-cols-[minmax(0,1fr)_10rem_8rem_6rem_12rem]"
              >
                <span className="col-span-2 min-w-0 md:col-span-1">
                  <span className="block truncate font-medium text-primary">{a.title}</span>
                  <span className="block truncate text-xs text-muted">{a.creator_name}</span>
                </span>
                <span>
                  <StatusBadge tone={AUCTION_TONE[a.status] ?? "progress"}>{ts(a.status)}</StatusBadge>
                </span>
                <span className="text-sm tabular-nums">
                  <bdi dir="ltr">{formatUsd(a.current_price ?? a.starting_price)}</bdi>
                </span>
                <span className="text-sm text-muted tabular-nums">{a.bid_count}</span>
                <span className="text-xs text-muted">
                  {formatDateTime(a.status === "draft" || a.status === "scheduled" ? a.starts_at : a.ends_at)}
                </span>
              </Link>
            </li>
          ))}
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
