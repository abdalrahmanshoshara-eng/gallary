import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { OrderView } from "@/features/orders/OrderView";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("orders");
  return { title: t("title"), robots: { index: false } };
}

export default async function OrderPage({ params, searchParams }: PageProps<"/[locale]/orders/[number]">) {
  const [{ locale, number }, query] = await Promise.all([params, searchParams]);
  setRequestLocale(locale);
  if (!/^ART-\d{4}-\d{6}$/.test(number)) notFound();
  await requireCustomer(locale, `/orders/${number}`);
  return (
    <Container className="py-12">
      <AccountTabs />
      <OrderView number={number} justCreated={query.created === "1"} />
    </Container>
  );
}
