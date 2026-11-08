"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";

import { listPages, pagesKey } from "./api";

export function PagesList() {
  const t = useTranslations("admin.content.pages");
  const tc = useTranslations("common");
  const pages = useQuery({ queryKey: pagesKey, queryFn: listPages });
  if (pages.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (pages.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  return (
    <ul className="divide-y divide-border/60 border-y border-border/60">
      {pages.data.map((page) => (
        <li key={page.slug} className="flex flex-wrap items-center justify-between gap-4 py-4">
          <div className="min-w-0">
            <Link href={`/admin/content/pages/${page.slug}`} className="text-lg text-primary hover:text-secondary">
              {page.label}
            </Link>
            <p className="mt-1 text-xs text-muted">
              {page.published
                ? t("status.published", { number: page.published.number, date: formatDateTime(page.published.published_at) })
                : t("status.unpublished")}
            </p>
            {!page.can_edit ? <p className="mt-1 text-xs text-muted">{t("readOnly")}</p> : null}
          </div>
          <span className="flex items-center gap-3">
            {page.unpublished_changes ? <StatusBadge tone="action">{t("status.changes")}</StatusBadge> : null}
            <Link
              href={`/admin/content/pages/${page.slug}`}
              className="inline-flex min-h-10 items-center rounded-[var(--radius-control)] border border-secondary px-4 text-sm text-primary hover:bg-surface"
            >
              {page.can_edit ? t("edit") : t("view")}
            </Link>
          </span>
        </li>
      ))}
    </ul>
  );
}
