import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { requireStaff } from "@/lib/auth/require";
import { isCatalogEditor } from "@/lib/auth/types";

export default async function AdminHomePage({ params }: PageProps<"/[locale]/admin">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireStaff(locale, "/admin");
  const t = await getTranslations("admin");
  const sections = [
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
        <section className="mt-10">
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
