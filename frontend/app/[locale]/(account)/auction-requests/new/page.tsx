import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { RequestForm } from "@/features/auction-requests/RequestForm";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auctionRequests");
  return { title: t("newTitle"), robots: { index: false } };
}

export default async function NewAuctionRequestPage({ params }: PageProps<"/[locale]/auction-requests/new">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/auction-requests/new");
  const t = await getTranslations("auctionRequests");
  return (
    <Container className="py-12">
      <AccountTabs />
      <div className="max-w-3xl">
        <h1 className="text-3xl font-semibold text-primary">{t("newTitle")}</h1>
        <p className="mt-2 mb-10 text-sm text-muted">{t("newIntro")}</p>
        <RequestForm />
      </div>
    </Container>
  );
}
