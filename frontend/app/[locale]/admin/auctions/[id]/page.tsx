import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuctionManager } from "@/features/admin-auctions/AuctionManager";
import { Link } from "@/i18n/navigation";
import { requireAuctionStaff } from "@/lib/auth/require";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function AdminAuctionPage({ params, searchParams }: PageProps<"/[locale]/admin/auctions/[id]">) {
  const [{ locale, id }, query] = await Promise.all([params, searchParams]);
  setRequestLocale(locale);
  if (!UUID.test(id)) notFound();
  await requireAuctionStaff(locale, `/admin/auctions/${id}`);
  const t = await getTranslations("admin.auctions");
  return (
    <>
      <Link href="/admin/auctions" className="mb-4 inline-block text-sm text-muted hover:text-secondary">
        {t("title")}
      </Link>
      <AuctionManager id={id} justCreated={query.created === "1"} />
    </>
  );
}
