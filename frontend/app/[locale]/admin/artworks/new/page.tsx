import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworkForm } from "@/features/admin-catalog/ArtworkForm";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function NewArtworkPage({ params }: PageProps<"/[locale]/admin/artworks/new">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/artworks/new");
  const t = await getTranslations("admin.artworks");
  const tc = await getTranslations("common");
  return (
    <>
      <Link href="/admin/artworks" className="text-sm text-muted hover:text-primary">
        {tc("back")}
      </Link>
      <h1 className="mt-2 mb-10 text-3xl font-semibold text-primary">{t("new")}</h1>
      <ArtworkForm />
    </>
  );
}
