import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { RequestsList } from "@/features/auction-requests/RequestsList";
import { Link } from "@/i18n/navigation";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auctionRequests");
  return { title: t("title"), robots: { index: false } };
}

export default async function AuctionRequestsPage({ params }: PageProps<"/[locale]/auction-requests">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/auction-requests");
  const t = await getTranslations("auctionRequests");
  return (
    <Container className="py-12">
      <AccountTabs />
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-xl">
          <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
          <p className="mt-2 text-sm text-muted">{t("intro")}</p>
        </div>
        <Link
          href="/auction-requests/new"
          className="inline-flex min-h-11 items-center gap-2 rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary hover:bg-primary/90"
        >
          <Icon name="plus" className="size-4" />
          {t("new")}
        </Link>
      </div>
      <RequestsList />
    </Container>
  );
}
