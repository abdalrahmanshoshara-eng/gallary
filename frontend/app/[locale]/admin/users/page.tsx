import { getTranslations, setRequestLocale } from "next-intl/server";

import { UsersTable } from "@/features/admin/UsersTable";
import { requireSuperAdmin } from "@/lib/auth/require";

export default async function UsersPage({ params }: PageProps<"/[locale]/admin/users">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireSuperAdmin(locale, "/admin/users");
  const t = await getTranslations("admin.users");
  return (
    <>
      <h1 className="mb-10 text-3xl font-semibold text-primary">{t("title")}</h1>
      <UsersTable currentUserId={user.id} />
    </>
  );
}
