import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

type Props = {
  pathname: string;
  page: number;
  totalPages: number;
  /** Other query parameters to keep when changing page. */
  query?: Record<string, string | string[] | undefined>;
};

/** Link-based pagination: crawlable, works without JavaScript, keeps filters. */
export async function Pagination({ pathname, page, totalPages, query = {} }: Props) {
  if (totalPages <= 1) return null;
  const t = await getTranslations("common");
  const href = (p: number) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...query, page: p > 1 ? String(p) : undefined })) {
      for (const item of Array.isArray(value) ? value : [value]) if (item) params.append(key, item);
    }
    const qs = params.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };
  const linkClass = "rounded-[var(--radius-control)] px-4 py-2 text-primary hover:bg-surface";
  return (
    <nav aria-label={t("pagination")} className="mt-16 flex items-center justify-center gap-4 text-sm">
      {page > 1 ? (
        <Link href={href(page - 1)} className={linkClass} rel="prev">
          {t("previous")}
        </Link>
      ) : null}
      <span className="text-muted">{t("pageOf", { page, total: totalPages })}</span>
      {page < totalPages ? (
        <Link href={href(page + 1)} className={linkClass} rel="next">
          {t("next")}
        </Link>
      ) : null}
    </nav>
  );
}
