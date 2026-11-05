import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { CartView } from "@/features/cart/CartView";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("cart");
  return { title: t("title"), robots: { index: false } };
}

export default async function CartPage({ params }: PageProps<"/[locale]/cart">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/cart");
  const t = await getTranslations("cart");
  return (
    <Container className="py-12">
      <h1 className="mb-8 text-3xl font-semibold text-primary">{t("title")}</h1>
      <CartView />
    </Container>
  );
}
