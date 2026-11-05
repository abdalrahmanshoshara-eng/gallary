import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { OrdersList } from "@/features/orders/OrdersList";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("orders");
  return { title: t("title"), robots: { index: false } };
}

export default async function OrdersPage({ params }: PageProps<"/[locale]/orders">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/orders");
  const t = await getTranslations("orders");
  return (
    <Container className="py-12">
      <AccountTabs />
      <h1 className="mb-8 text-3xl font-semibold text-primary">{t("title")}</h1>
      <OrdersList />
    </Container>
  );
}
