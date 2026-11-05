import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { RequestReview } from "@/features/admin-auctions/RequestReview";
import { Link } from "@/i18n/navigation";
import { requireAuctionStaff } from "@/lib/auth/require";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function AdminAuctionRequestPage({ params }: PageProps<"/[locale]/admin/auction-requests/[id]">) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  if (!UUID.test(id)) notFound();
  await requireAuctionStaff(locale, `/admin/auction-requests/${id}`);
  const t = await getTranslations("admin.auctionRequests");
  return (
    <>
      <Link href="/admin/auction-requests" className="mb-4 inline-block text-sm text-muted hover:text-secondary">
        {t("title")}
      </Link>
      <RequestReview id={id} />
    </>
  );
}
