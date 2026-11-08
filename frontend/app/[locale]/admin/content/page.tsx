import { setRequestLocale } from "next-intl/server";

import { PagesList } from "@/features/admin-content/PagesList";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function Page({ params }: PageProps<"/[locale]/admin/content">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/content");
  return <PagesList />;
}
