import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { requireStaff } from "@/lib/auth/require";

export default async function AdminHomePage({ params }: PageProps<"/[locale]/admin">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireStaff(locale, "/admin");
  const t = await getTranslations("admin");

  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 text-muted">
        {user.display_name} · {user.roles.map((r) => t(`roles.${r as "super_admin"}`)).join("، ")}
      </p>
      {user.is_super_admin ? (
        <section className="mt-10">
          <h2 className="mb-4 text-lg font-medium text-primary">{t("availableSections")}</h2>
          <ul className="grid gap-4 md:grid-cols-2">
            <li className="rounded-[var(--radius-card)] border border-border/60 p-6">
              <Link href="/admin/staff" className="text-lg text-primary hover:text-secondary">
                {t("staff.title")}
              </Link>
              <p className="mt-2 text-sm text-muted">{t("staff.intro")}</p>
            </li>
            <li className="rounded-[var(--radius-card)] border border-border/60 p-6">
              <Link href="/admin/users" className="text-lg text-primary hover:text-secondary">
                {t("users.title")}
              </Link>
            </li>
          </ul>
        </section>
      ) : (
        <p className="mt-10 text-muted">{t("noSections")}</p>
      )}
    </>
  );
}
