"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";

const TABS = [
  { href: "/account", key: "account" },
  { href: "/orders", key: "orders" },
  { href: "/bids", key: "bids" },
  { href: "/auction-requests", key: "auctionRequests" },
  { href: "/favorites", key: "favorites" },
] as const;

/** Customer account navigation; staff accounts only have the profile page, so no tabs. */
export function AccountTabs() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const { data: user } = useCurrentUser();
  if (!user || user.is_staff) return null;
  return (
    <nav aria-label={t("accountSection")} className="mb-10 border-b border-border/60">
      <ul className="-mb-px flex gap-6 overflow-x-auto">
        {TABS.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`inline-block border-b-2 py-3 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                  active ? "border-primary font-medium text-primary" : "border-transparent text-muted hover:text-primary"
                }`}
              >
                {t(tab.key)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
