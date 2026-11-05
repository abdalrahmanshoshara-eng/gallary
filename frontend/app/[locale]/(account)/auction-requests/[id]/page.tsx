import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { RequestView } from "@/features/auction-requests/RequestView";
import { requireCustomer } from "@/lib/auth/require";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auctionRequests");
  return { title: t("title"), robots: { index: false } };
}

export default async function AuctionRequestPage({ params, searchParams }: PageProps<"/[locale]/auction-requests/[id]">) {
  const [{ locale, id }, query] = await Promise.all([params, searchParams]);
  setRequestLocale(locale);
  if (!UUID.test(id)) notFound();
  await requireCustomer(locale, `/auction-requests/${id}`);
  return (
    <Container className="py-12">
      <AccountTabs />
      <div className="max-w-3xl">
        <RequestView id={id} justSubmitted={query.submitted === "1"} />
      </div>
    </Container>
  );
}
