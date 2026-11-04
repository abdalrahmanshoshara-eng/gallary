import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtistForm } from "@/features/admin-catalog/ArtistForm";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function NewArtistPage({ params }: PageProps<"/[locale]/admin/artists/new">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, "/admin/artists/new");
  const t = await getTranslations("admin.artists");
  const tc = await getTranslations("common");
  return (
    <>
      <Link href="/admin/artists" className="text-sm text-muted hover:text-primary">
        {tc("back")}
      </Link>
      <h1 className="mt-2 mb-10 text-3xl font-semibold text-primary">{t("new")}</h1>
      <ArtistForm />
    </>
  );
}
