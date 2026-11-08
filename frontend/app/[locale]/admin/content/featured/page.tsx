import { setRequestLocale } from "next-intl/server";

import { FeaturedManager } from "@/features/admin-content/FeaturedManager";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function Page({ params }: PageProps<"/[locale]/admin/content/featured">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/content/featured");
  return <FeaturedManager />;
}
