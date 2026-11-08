"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { dashboardKey, getDashboard, type Dashboard as DashboardData } from "./api";

const PERIODS = ["30d", "90d", "all"] as const;
type Period = (typeof PERIODS)[number];
type Href = Parameters<typeof Link>[0]["href"];

function Kpi({ label, value, sub, href, scope }: { label: string; value: ReactNode; sub?: ReactNode; href: Href; scope: string }) {
  return (
    <Link href={href} className="group flex flex-col gap-1 rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-4 transition-colors duration-300 ease-calm hover:border-secondary">
      <span className="flex items-center justify-between gap-2 text-sm text-muted">
        {label}
        <span className="rounded-full bg-surface px-2 py-0.5 text-[11px]">{scope}</span>
      </span>
      <span className="text-2xl font-semibold text-primary tabular-nums">{value}</span>
      {sub ? <span className="text-xs text-muted">{sub}</span> : null}
    </Link>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-base font-medium text-primary">{title}</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
    </section>
  );
}

function Attention({ items }: { items: DashboardData["attention"] }) {
  const t = useTranslations("admin.dashboard");
  const link = (item: DashboardData["attention"][number]): Href =>
    item.kind === "order_expiring"
      ? `/admin/orders/${item.ref}`
      : item.kind === "auction_awaiting_winner"
        ? `/admin/auctions/${item.ref}`
        : item.kind === "auction_requests_new"
          ? "/admin/auction-requests"
          : "/admin/settlements";
  return (
    <section aria-labelledby="attention" className="rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-5">
      <h2 id="attention" className="mb-3 flex items-center gap-2 text-base font-medium text-primary">
        <Icon name="clock" className="size-4" />
        {t("attention")}
      </h2>
      {items.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-olive">
          <Icon name="check" className="size-4" />
          {t("nothingUrgent")}
        </p>
      ) : (
        <ul className="divide-y divide-border/50">
          {items.map((item, index) => (
            <li key={`${item.kind}-${item.ref}-${index}`}>
              <Link href={link(item)} className="block py-2.5 text-sm text-text hover:text-primary">
                {t(`items.${item.kind}`, {
                  ref: item.ref,
                  label: item.label,
                  count: item.count ?? 0,
                  time: item.at ? formatDateTime(item.at) : "",
                })}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Admin home (§9.1): what needs action first, then the figures for the sections the staff
 * member works in. Balances are "now"; flows follow the chosen period, and each card says which.
 */
export function Dashboard() {
  const t = useTranslations("admin.dashboard");
  const tsum = useTranslations("admin.settlements.summary");
  const [period, setPeriod] = useState<Period>("30d");
  const dashboard = useQuery({ queryKey: dashboardKey(period), queryFn: () => getDashboard(period), refetchInterval: 60_000 });

  if (dashboard.isError) {
    return (
      <Alert tone="error">
        {t("loadError")}{" "}
        <button type="button" className="underline" onClick={() => void dashboard.refetch()}>
          {t("refresh")}
        </button>
      </Alert>
    );
  }
  const d = dashboard.data;
  const now = t("now");
  const inPeriod = t(`periods.${period}`);

  return (
    <div className="flex flex-col gap-8" aria-busy={dashboard.isFetching || undefined}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label={t("period")} className="flex gap-2">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              role="tab"
              aria-selected={period === p}
              onClick={() => setPeriod(p)}
              className={`rounded-full border px-4 py-1.5 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                period === p ? "border-primary bg-primary text-on-primary" : "border-border hover:border-secondary"
              }`}
            >
              {t(`periods.${p}`)}
            </button>
          ))}
        </div>
        {d ? (
          <span className="flex items-center gap-3 text-xs text-muted">
            {t("updated", { time: formatDateTime(d.generated_at) })}
            <Button variant="ghost" className="min-h-9 px-3" onClick={() => void dashboard.refetch()}>
              {t("refresh")}
            </Button>
          </span>
        ) : null}
      </div>

      {!d ? (
        <div className="grid gap-4 sm:grid-cols-3" aria-hidden>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-[var(--radius-card)] bg-surface/60" />
          ))}
        </div>
      ) : (
        <>
          <Attention items={d.attention} />
          {d.orders ? (
            <Section title={t("orders")}>
              <Kpi
                label={t("kpi.sales")}
                scope={inPeriod}
                href="/admin/orders"
                value={<bdi dir="ltr">{formatUsd(d.orders.sales_amount)}</bdi>}
                sub={t("kpi.sales_count", { count: d.orders.sales_count })}
              />
              <Kpi label={t("kpi.commission_amount")} scope={inPeriod} href="/admin/settlements" value={<bdi dir="ltr">{formatUsd(d.orders.commission_amount)}</bdi>} />
              <Kpi label={t("kpi.orders")} scope={inPeriod} href="/admin/orders" value={d.orders.orders} />
              <Kpi label={t("kpi.pending_deposit")} scope={now} href="/admin/orders" value={d.orders.pending_deposit} />
            </Section>
          ) : null}
          {d.settlements ? (
            <Section title={t("settlements")}>
              <Kpi
                label={t("kpi.pending_settlements")}
                scope={now}
                href="/admin/settlements"
                value={<bdi dir="ltr">{formatUsd(d.settlements.pending_amount)}</bdi>}
                sub={tsum("items", { count: d.settlements.pending_count })}
              />
            </Section>
          ) : null}
          {d.auctions ? (
            <Section title={t("auctions")}>
              <Kpi label={t("kpi.live")} scope={now} href="/admin/auctions" value={d.auctions.live} />
              <Kpi label={t("kpi.upcoming")} scope={now} href="/admin/auctions" value={d.auctions.upcoming} />
              <Kpi label={t("kpi.ended")} scope={inPeriod} href="/admin/auctions" value={d.auctions.ended} />
            </Section>
          ) : null}
          {d.catalog ? (
            <Section title={t("catalog")}>
              <Kpi label={t("kpi.published_artworks")} scope={now} href="/admin/artworks" value={d.catalog.published_artworks} />
              <Kpi label={t("kpi.available_artworks")} scope={now} href="/artworks" value={d.catalog.available_artworks} />
            </Section>
          ) : null}
        </>
      )}
    </div>
  );
}
