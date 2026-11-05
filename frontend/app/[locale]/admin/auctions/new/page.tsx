import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuctionForm } from "@/features/admin-auctions/AuctionForm";
import { Link } from "@/i18n/navigation";
import { requireAuctionStaff } from "@/lib/auth/require";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function NewAuctionPage({ params, searchParams }: PageProps<"/[locale]/admin/auctions/new">) {
  const [{ locale }, query] = await Promise.all([params, searchParams]);
  setRequestLocale(locale);
  await requireAuctionStaff(locale, "/admin/auctions/new");
  const t = await getTranslations("admin.auctions");
  const requestId = typeof query.request === "string" && UUID.test(query.request) ? query.request : undefined;
  return (
    <div className="max-w-3xl">
      <Link href="/admin/auctions" className="text-sm text-muted hover:text-secondary">
        {t("title")}
      </Link>
      <h1 className="mt-2 mb-8 text-3xl font-semibold text-primary">{t("newTitle")}</h1>
      <AuctionForm requestId={requestId} />
    </div>
  );
}
