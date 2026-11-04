import { getTranslations, setRequestLocale } from "next-intl/server";

import { TermsManager } from "@/features/admin-catalog/TermsManager";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function CatalogTermsPage({ params }: PageProps<"/[locale]/admin/catalog">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/catalog");
  const t = await getTranslations("admin.terms");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-10 text-muted">{t("intro")}</p>
      <TermsManager />
    </>
  );
}
