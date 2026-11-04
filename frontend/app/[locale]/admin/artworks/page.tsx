import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworksTable } from "@/features/admin-catalog/ArtworksTable";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function AdminArtworksPage({ params }: PageProps<"/[locale]/admin/artworks">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/artworks");
  const t = await getTranslations("admin.artworks");
  return (
    <>
      <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
        <Link
          href="/admin/artworks/new"
          className="inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-primary px-6 text-on-primary hover:bg-primary/90"
        >
          {t("new")}
        </Link>
      </div>
      <ArtworksTable />
    </>
  );
}
