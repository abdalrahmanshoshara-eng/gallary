import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtistsTable } from "@/features/admin-catalog/ArtistsTable";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function AdminArtistsPage({ params }: PageProps<"/[locale]/admin/artists">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/artists");
  const t = await getTranslations("admin.artists");
  return (
    <>
      <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
        <Link
          href="/admin/artists/new"
          className="inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-primary px-6 text-on-primary hover:bg-primary/90"
        >
          {t("new")}
        </Link>
      </div>
      <ArtistsTable />
    </>
  );
}
