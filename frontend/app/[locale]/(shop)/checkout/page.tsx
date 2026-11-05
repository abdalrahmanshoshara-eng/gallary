import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { CheckoutForm } from "@/features/orders/CheckoutForm";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("checkout");
  return { title: t("title"), robots: { index: false } };
}

export default async function CheckoutPage({ params }: PageProps<"/[locale]/checkout">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireCustomer(locale, "/checkout");
  const t = await getTranslations("checkout");
  return (
    <Container className="py-12">
      <h1 className="mb-8 text-3xl font-semibold text-primary">{t("title")}</h1>
      <CheckoutForm user={user} />
    </Container>
  );
}
