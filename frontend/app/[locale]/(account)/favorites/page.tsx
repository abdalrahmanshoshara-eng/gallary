import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { FavoritesList } from "@/features/favorites/FavoritesList";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("favorites");
  return { title: t("title"), robots: { index: false } };
}

export default async function FavoritesPage({ params }: PageProps<"/[locale]/favorites">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/favorites");
  const t = await getTranslations("favorites");
  return (
    <Container className="py-12">
      <AccountTabs />
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-3 mb-10 text-muted">{t("intro")}</p>
      <FavoritesList />
    </Container>
  );
}
