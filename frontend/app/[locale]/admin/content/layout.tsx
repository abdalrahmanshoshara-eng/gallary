import { getTranslations } from "next-intl/server";

import { ContentTabs } from "@/features/admin-content/ContentTabs";

export default async function ContentLayout({ children }: LayoutProps<"/[locale]/admin/content">) {
  const t = await getTranslations("admin.content");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-6 text-muted">{t("intro")}</p>
      <ContentTabs />
      {children}
    </>
  );
}
