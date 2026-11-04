import { getTranslations, setRequestLocale } from "next-intl/server";

import { SettingsForm } from "@/features/admin-catalog/SettingsForm";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function SettingsPage({ params }: PageProps<"/[locale]/admin/settings">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireCatalogEditor(locale, "/admin/settings");
  const t = await getTranslations("admin.settings");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-10 text-muted">{t("intro")}</p>
      <SettingsForm editable={user.is_super_admin} />
    </>
  );
}
