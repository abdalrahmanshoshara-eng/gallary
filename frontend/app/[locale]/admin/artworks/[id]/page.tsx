import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import type { AdminArtwork } from "@/features/admin-catalog/api";
import { ArtworkEditor } from "@/features/admin-catalog/ArtworkEditor";
import { isUuid, loadAdmin } from "@/features/admin-catalog/load";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function EditArtworkPage({ params, searchParams }: PageProps<"/[locale]/admin/artworks/[id]">) {
  const [{ locale, id }, query] = await Promise.all([params, searchParams]);
  setRequestLocale(locale);
  await requireCatalogEditor(locale, `/admin/artworks/${id}`);
  if (!isUuid(id)) notFound();
  const artwork = await loadAdmin<AdminArtwork>(`/admin/artworks/${id}`);
  const tc = await getTranslations("common");
  return (
    <>
      <Link href="/admin/artworks" className="text-sm text-muted hover:text-primary">
        {tc("back")}
      </Link>
      <h1 className="mt-2 mb-10 text-3xl font-semibold text-primary">{artwork.title}</h1>
      <ArtworkEditor initial={artwork} justCreated={query.created === "1"} />
    </>
  );
}
