import { getTranslations, setRequestLocale } from "next-intl/server";

import { Icon } from "@/components/ui/Icon";
import { AuctionsTable } from "@/features/admin-auctions/AuctionsTable";
import { Link } from "@/i18n/navigation";
import { requireAuctionStaff } from "@/lib/auth/require";

export default async function AdminAuctionsPage({ params }: PageProps<"/[locale]/admin/auctions">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireAuctionStaff(locale, "/admin/auctions");
  const t = await getTranslations("admin.auctions");
  return (
    <>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
          <p className="mt-2 text-muted">{t("intro")}</p>
        </div>
        <Link
          href="/admin/auctions/new"
          className="inline-flex min-h-11 items-center gap-2 rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary hover:bg-primary/90"
        >
          <Icon name="plus" className="size-4" />
          {t("new")}
        </Link>
      </div>
      <AuctionsTable />
    </>
  );
}
