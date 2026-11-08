import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { requireStaff } from "@/lib/auth/require";
import { Dashboard } from "@/features/admin-finance/Dashboard";
import { canUseOrderDesk, isAuctionStaff, isCatalogEditor, isOrdersStaff } from "@/lib/auth/types";

export default async function AdminHomePage({ params }: PageProps<"/[locale]/admin">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireStaff(locale, "/admin");
  const t = await getTranslations("admin");
  const sections = [
    ...(canUseOrderDesk(user)
      ? [{ href: "/admin/orders" as const, title: t("orders.title"), intro: t("orders.intro") }]
      : []),
    ...(isOrdersStaff(user)
      ? [{ href: "/admin/settlements" as const, title: t("settlements.title"), intro: t("settlements.intro") }]
      : []),
    ...(isAuctionStaff(user)
      ? [
          { href: "/admin/auctions" as const, title: t("auctions.title"), intro: t("auctions.intro") },
          { href: "/admin/auction-requests" as const, title: t("auctionRequests.title"), intro: t("auctionRequests.intro") },
        ]
      : []),
    ...(isCatalogEditor(user)
      ? [
          { href: "/admin/artworks" as const, title: t("artworks.title"), intro: t("artworks.homeIntro") },
          { href: "/admin/artists" as const, title: t("artists.title"), intro: t("artists.homeIntro") },
          { href: "/admin/catalog" as const, title: t("terms.title"), intro: t("terms.intro") },
          { href: "/admin/settings" as const, title: t("settings.title"), intro: t("settings.intro") },
        ]
      : []),
    ...(user.is_super_admin
      ? [
          { href: "/admin/staff" as const, title: t("staff.title"), intro: t("staff.intro") },
          { href: "/admin/users" as const, title: t("users.title"), intro: "" },
          { href: "/admin/audit" as const, title: t("audit.title"), intro: t("audit.intro") },
        ]
      : []),
  ];

  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 text-muted">
        {user.display_name} · {user.roles.map((r) => t(`roles.${r as "super_admin"}`)).join("، ")}
      </p>
      {sections.length ? (
        <div className="mt-8">
          <Dashboard />
        </div>
      ) : null}
      {sections.length ? (
        <section className="mt-12">
          <h2 className="mb-4 text-lg font-medium text-primary">{t("availableSections")}</h2>
          <ul className="grid gap-4 md:grid-cols-2">
            {sections.map((section) => (
              <li key={section.href} className="rounded-[var(--radius-card)] border border-border/60 p-6">
                <Link href={section.href} className="text-lg text-primary hover:text-secondary">
                  {section.title}
                </Link>
                {section.intro ? <p className="mt-2 text-sm text-muted">{section.intro}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="mt-10 text-muted">{t("noSections")}</p>
      )}
    </>
  );
}
