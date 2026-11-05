import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { OrderManager } from "@/features/admin-orders/OrderManager";
import { Link } from "@/i18n/navigation";
import { requireOrderDesk } from "@/lib/auth/require";

export default async function AdminOrderPage({ params }: PageProps<"/[locale]/admin/orders/[number]">) {
  const { locale, number } = await params;
  setRequestLocale(locale);
  if (!/^ART-\d{4}-\d{6}$/.test(number)) notFound();
  await requireOrderDesk(locale, `/admin/orders/${number}`);
  const tc = await getTranslations("common");
  return (
    <>
      <Link href="/admin/orders" className="mb-4 inline-block text-sm text-muted hover:text-primary">
        {tc("back")}
      </Link>
      <OrderManager number={number} />
    </>
  );
}
