"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { requestTone } from "@/features/auction-requests/tone";
import { Link } from "@/i18n/navigation";
import { pageCount } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { adminRequestsKey, listAdminRequests } from "./api";

const FILTERS = ["open", "submitted", "under_review", "needs_more_info", "negotiation", "approved", "rejected", "withdrawn", "all"] as const;
type Filter = (typeof FILTERS)[number];

/** Review queue: requests needing attention, oldest waiting first. */
export function RequestsQueue() {
  const t = useTranslations("admin.auctionRequests");
  const tr = useTranslations("auctionRequests.status");
  const tc = useTranslations("common");
  const [filter, setFilter] = useState<Filter>("open");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const params = { status: filter, search: debounced, page };
  const requests = useQuery({
    queryKey: adminRequestsKey(params),
    queryFn: () => listAdminRequests(params),
    placeholderData: keepPreviousData,
  });
  const totalPages = requests.data ? pageCount(requests.data.count) : 1;

  return (
    <div className="flex flex-col gap-6">
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

      {requests.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {requests.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {requests.data && requests.data.results.length === 0 ? <p className="py-10 text-center text-muted">{t("empty")}</p> : null}
      {requests.data && requests.data.results.length > 0 ? (
        <ul className="divide-y divide-border/60 border-y border-border/60" aria-busy={requests.isFetching || undefined}>
          {requests.data.results.map((r) => (
            <li key={r.id}>
              <Link
                href={`/admin/auction-requests/${r.id}`}
                className="grid grid-cols-2 items-center gap-x-4 gap-y-2 py-4 hover:bg-surface/40 md:grid-cols-[minmax(0,1fr)_12rem_9rem_10rem]"
              >
                <span className="col-span-2 min-w-0 md:col-span-1">
                  <span className="block truncate font-medium text-primary">{r.work_title}</span>
                  <span className="block truncate text-xs text-muted">
                    {r.artist_name} · {r.customer} · <bdi dir="ltr">{r.contact_phone}</bdi>
                  </span>
                </span>
                <span>
                  <StatusBadge tone={requestTone(r.status)}>{tr(r.status)}</StatusBadge>
                </span>
                <span className="text-sm tabular-nums">{r.expected_price ? <bdi dir="ltr">{formatUsd(r.expected_price)}</bdi> : t("noExpected")}</span>
                <span className="text-xs text-muted">{t("submittedOn", { date: formatDateTime(r.created_at) })}</span>
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
