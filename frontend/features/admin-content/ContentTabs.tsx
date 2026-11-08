"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

const TABS = [
  { href: "/admin/content", key: "pages" },
  { href: "/admin/content/faq", key: "faq" },
  { href: "/admin/content/banners", key: "banners" },
  { href: "/admin/content/featured", key: "featured" },
] as const;

export function ContentTabs() {
  const t = useTranslations("admin.content");
  const pathname = usePathname();
  return (
    <nav aria-label={t("tabsLabel")} className="mb-8 border-b border-border/60">
      <ul className="-mb-px flex gap-6 overflow-x-auto">
        {TABS.map((tab) => {
          const active = tab.href === "/admin/content" ? pathname === tab.href || pathname.startsWith("/admin/content/pages") : pathname.startsWith(tab.href);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`inline-block border-b-2 py-3 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                  active ? "border-primary font-medium text-primary" : "border-transparent text-muted hover:text-primary"
                }`}
              >
                {t(`tabs.${tab.key}`)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Up/down reorder buttons shared by the content lists. */
export function MoveButtons({ first, last, upLabel, downLabel, onMove, busy }: { first: boolean; last: boolean; upLabel: string; downLabel: string; onMove: (d: "up" | "down") => void; busy?: boolean }) {
  const cls = "inline-flex size-9 items-center justify-center rounded-full text-primary hover:bg-surface disabled:opacity-30";
  return (
    <span className="flex gap-1">
      <button type="button" className={cls} disabled={first || busy} aria-label={upLabel} onClick={() => onMove("up")}>
        <span aria-hidden>↑</span>
      </button>
      <button type="button" className={cls} disabled={last || busy} aria-label={downLabel} onClick={() => onMove("down")}>
        <span aria-hidden>↓</span>
      </button>
    </span>
  );
}
