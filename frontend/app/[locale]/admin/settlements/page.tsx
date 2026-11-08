import { getTranslations, setRequestLocale } from "next-intl/server";

import { SettlementsManager } from "@/features/admin-finance/SettlementsManager";
import { requireOrdersStaff } from "@/lib/auth/require";

export default async function SettlementsPage({ params }: PageProps<"/[locale]/admin/settlements">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireOrdersStaff(locale, "/admin/settlements");
  const t = await getTranslations("admin.settlements");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-8 text-muted">{t("intro")}</p>
      <SettlementsManager />
    </>
  );
}
