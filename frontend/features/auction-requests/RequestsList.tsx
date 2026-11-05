"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Icon } from "@/components/ui/Icon";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";

import { listRequests, requestsKey } from "./api";
import { requestTone } from "./tone";

export function RequestsList() {
  const t = useTranslations("auctionRequests");
  const tc = useTranslations("common");
  const requests = useQuery({ queryKey: requestsKey, queryFn: listRequests });

  if (requests.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy>
        {[0, 1].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-[var(--radius-card)] bg-surface/60" />
        ))}
      </div>
    );
  }
  if (requests.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  if (requests.data.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <Icon name="plus" className="size-12 text-secondary" />
        <p className="text-lg text-primary">{t("empty")}</p>
        <p className="max-w-sm text-sm text-muted">{t("emptyHint")}</p>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-4">
      {requests.data.map((request) => {
        const needsMe = request.status === "needs_more_info";
        return (
          <li key={request.id}>
            <Link
              href={`/auction-requests/${request.id}`}
              className={`flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-card)] border p-5 transition-colors duration-300 ease-calm hover:border-secondary ${
                needsMe ? "border-secondary/60 bg-white/70" : "border-border/60"
              }`}
            >
              <div className="min-w-0">
                <p className="font-medium text-primary">{request.work_title}</p>
                <p className="mt-1 text-sm text-muted">
                  {request.artist_name} · {t("submittedOn", { date: formatDateTime(request.created_at) })}
                </p>
                {needsMe ? <p className="mt-1 text-xs text-primary">{t("statusHelp.needs_more_info")}</p> : null}
              </div>
              <StatusBadge tone={requestTone(request.status)}>{t(`status.${request.status}`)}</StatusBadge>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
