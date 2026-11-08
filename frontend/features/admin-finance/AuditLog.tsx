"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { pageCount } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";

import { auditKey, getAuditFacets, listAudit, type AuditEntry } from "./api";

const field = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";
const EMPTY = { entity_type: "", action: "", actor: "", system: "", from: "", to: "", search: "" };

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

/** Change entries as "field: from → to" when shaped that way, otherwise key: value. */
function Changes({ changes }: { changes: AuditEntry["changes"] }) {
  const t = useTranslations("admin.audit");
  const entries = Object.entries((changes ?? {}) as Record<string, unknown>);
  if (!entries.length) return <p className="text-xs text-muted">{t("noChanges")}</p>;
  return (
    <dl className="grid gap-1 text-xs sm:grid-cols-[10rem_minmax(0,1fr)]">
      {entries.map(([key, value]) => {
        const pair = value && typeof value === "object" && "from" in value && "to" in value ? (value as { from: unknown; to: unknown }) : null;
        return (
          <div key={key} className="contents">
            <dt className="font-medium text-muted" dir="ltr">
              {key}
            </dt>
            <dd className="break-words" dir="auto">
              {pair ? (
                <>
                  <span className="line-through opacity-70">{show(pair.from)}</span> ← {show(pair.to)}
                </>
              ) : (
                show(value)
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** BR-007: the Super Admin's read-only view of every administrative and financial action. */
export function AuditLog() {
  const t = useTranslations("admin.audit");
  const tc = useTranslations("common");
  const [filters, setFilters] = useState(EMPTY);
  const [debounced, setDebounced] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(filters), 350);
    return () => clearTimeout(timer);
  }, [filters]);
  const params = { ...debounced, page };
  const facets = useQuery({ queryKey: ["admin", "audit", "facets"], queryFn: getAuditFacets, staleTime: 300_000 });
  const entries = useQuery({ queryKey: auditKey(params), queryFn: () => listAudit(params), placeholderData: keepPreviousData });
  const totalPages = entries.data ? pageCount(entries.data.count) : 1;
  const set = (key: keyof typeof EMPTY, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };
  const filtered = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-col gap-6">
      <fieldset className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <legend className="sr-only">{tc("search")}</legend>
        <label className="flex flex-col gap-1 text-sm">
          {t("entityType")}
          <select className={field} value={filters.entity_type} onChange={(e) => set("entity_type", e.target.value)} dir="ltr">
            <option value="">{t("allTypes")}</option>
            {facets.data?.entity_types.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("action")}
          <input className={field} dir="ltr" placeholder={t("actionPlaceholder")} value={filters.action} onChange={(e) => set("action", e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("actor")}
          <input className={field} value={filters.actor} onChange={(e) => set("actor", e.target.value)} disabled={filters.system === "1"} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("from")}
          <input type="date" className={field} dir="ltr" value={filters.from} onChange={(e) => set("from", e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("to")}
          <input type="date" className={field} dir="ltr" value={filters.to} onChange={(e) => set("to", e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {tc("search")}
          <input type="search" className={field} placeholder={t("search")} value={filters.search} onChange={(e) => set("search", e.target.value)} />
        </label>
        <div className="flex flex-wrap items-center gap-4 sm:col-span-2 lg:col-span-3">
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-[var(--color-primary)]" checked={filters.system === "1"} onChange={(e) => set("system", e.target.checked ? "1" : "")} />
            {t("systemOnly")}
          </label>
          {filtered ? (
            <Button variant="ghost" onClick={() => setFilters(EMPTY)}>
              {t("reset")}
            </Button>
          ) : null}
        </div>
      </fieldset>

      {entries.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {entries.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {entries.data && entries.data.results.length === 0 ? <p className="py-10 text-center text-muted">{t("empty")}</p> : null}
      {entries.data && entries.data.results.length > 0 ? (
        <ol className="divide-y divide-border/60 border-y border-border/60" aria-busy={entries.isFetching || undefined}>
          {entries.data.results.map((e) => {
            const expanded = open === e.id;
            return (
              <li key={e.id} className="py-3">
                <div className="grid gap-x-4 gap-y-1 text-sm md:grid-cols-[11rem_10rem_minmax(0,1fr)_auto]">
                  <time dateTime={e.created_at} className="text-xs text-muted">
                    {formatDateTime(e.created_at)}
                  </time>
                  <span className="truncate">{e.actor ?? <span className="text-muted">{t("system")}</span>}</span>
                  <span className="min-w-0">
                    <code className="text-xs font-medium text-primary" dir="ltr">
                      {e.action}
                    </code>
                    <span className="block truncate text-xs text-muted" dir="ltr">
                      {e.entity_type} · {e.entity_id}
                    </span>
                    {e.reason ? <span className="block text-xs">{e.reason}</span> : null}
                  </span>
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : e.id)}
                    className="justify-self-start text-xs text-primary underline-offset-4 hover:underline md:justify-self-end"
                  >
                    {expanded ? t("hideDetails") : t("details")}
                  </button>
                </div>
                {expanded ? (
                  <div className="mt-3 flex flex-col gap-2 rounded-[var(--radius-control)] bg-surface/50 p-3">
                    <p className="text-xs font-medium">{t("changes")}</p>
                    <Changes changes={e.changes} />
                    <p className="text-xs text-muted">
                      {t("requestId")}: <span dir="ltr">{e.request_id || "—"}</span>
                      {e.actor_phone ? (
                        <>
                          {" · "}
                          <bdi dir="ltr">{e.actor_phone}</bdi>
                        </>
                      ) : null}
                    </p>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
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
