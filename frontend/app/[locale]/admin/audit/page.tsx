import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuditLog } from "@/features/admin-finance/AuditLog";
import { requireSuperAdmin } from "@/lib/auth/require";

export default async function AuditPage({ params }: PageProps<"/[locale]/admin/audit">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireSuperAdmin(locale, "/admin/audit");
  const t = await getTranslations("admin.audit");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-8 text-muted">{t("intro")}</p>
      <AuditLog />
    </>
  );
}
