"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
import { orderTone, StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";

import { listOrders, ordersKey } from "./api";

export function OrdersList() {
  const t = useTranslations("orders");
  const ts = useTranslations("status_order");
  const tc = useTranslations("common");
  const orders = useQuery({ queryKey: ordersKey, queryFn: listOrders });

  if (orders.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-[var(--radius-card)] bg-surface/60" />
        ))}
      </div>
    );
  }
  if (orders.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  if (orders.data.results.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Icon name="bag" className="size-12 text-secondary" />
        <p className="text-lg text-primary">{t("empty")}</p>
        <p className="max-w-sm text-sm text-muted">{t("emptyHint")}</p>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-4">
      {orders.data.results.map((order) => (
        <li key={order.number}>
          <Link
            href={`/orders/${order.number}`}
            className={`flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-card)] border p-5 transition-colors duration-300 ease-calm hover:border-secondary ${
              order.needs_action ? "border-secondary/60 bg-white/70" : "border-border/60"
            }`}
          >
            <div className="min-w-0">
              <p className="font-medium text-primary" dir="ltr">
                {order.number}
              </p>
              <p className="mt-1 text-sm text-muted">
                {formatDateTime(order.created_at)} · {t("items", { count: order.item_count })}
              </p>
              {order.needs_action ? (
                <p className="mt-1 text-xs text-primary">{t("expiresAt", { date: formatDateTime(order.reservation_expires_at) })}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-4">
              <bdi dir="ltr" className="font-medium">
                {formatUsd(order.subtotal)}
              </bdi>
              <StatusBadge tone={orderTone(order.status)}>{ts(order.status as "expired")}</StatusBadge>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
