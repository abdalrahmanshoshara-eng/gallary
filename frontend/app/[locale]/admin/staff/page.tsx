import { getTranslations, setRequestLocale } from "next-intl/server";

import { StaffManager } from "@/features/admin/StaffManager";
import { requireSuperAdmin } from "@/lib/auth/require";

export default async function StaffPage({ params }: PageProps<"/[locale]/admin/staff">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireSuperAdmin(locale, "/admin/staff");
  const t = await getTranslations("admin.staff");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-10 text-muted">{t("intro")}</p>
      <StaffManager currentUserId={user.id} />
    </>
  );
}
