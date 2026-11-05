import { getTranslations, setRequestLocale } from "next-intl/server";

import { RequestsQueue } from "@/features/admin-auctions/RequestsQueue";
import { requireAuctionStaff } from "@/lib/auth/require";

export default async function AdminAuctionRequestsPage({ params }: PageProps<"/[locale]/admin/auction-requests">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireAuctionStaff(locale, "/admin/auction-requests");
  const t = await getTranslations("admin.auctionRequests");
  return (
    <>
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-2 mb-8 text-muted">{t("intro")}</p>
      <RequestsQueue />
    </>
  );
}
