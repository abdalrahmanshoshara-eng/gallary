import { getTranslations, setRequestLocale } from "next-intl/server";

import { OrdersTable } from "@/features/admin-orders/OrdersTable";
import { requireOrdersStaff } from "@/lib/auth/require";

export default async function AdminOrdersPage({ params }: PageProps<"/[locale]/admin/orders">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireOrdersStaff(locale, "/admin/orders");
  const t = await getTranslations("admin.orders");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-8 text-muted">{t("intro")}</p>
      <OrdersTable />
    </>
  );
}
