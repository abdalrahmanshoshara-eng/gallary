import { setRequestLocale } from "next-intl/server";

import { BannersManager } from "@/features/admin-content/BannersManager";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function Page({ params }: PageProps<"/[locale]/admin/content/banners">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/content/banners");
  return <BannersManager />;
}
