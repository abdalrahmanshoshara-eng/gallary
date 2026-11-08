import { setRequestLocale } from "next-intl/server";

import { FaqManager } from "@/features/admin-content/FaqManager";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function Page({ params }: PageProps<"/[locale]/admin/content/faq">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/content/faq");
  return <FaqManager />;
}
