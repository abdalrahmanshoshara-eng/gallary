import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import type { AdminArtist } from "@/features/admin-catalog/api";
import { ArtistDelete } from "@/features/admin-catalog/ArtistDelete";
import { ArtistForm } from "@/features/admin-catalog/ArtistForm";
import { ArtistPhoto } from "@/features/admin-catalog/ArtistPhoto";
import { isUuid, loadAdmin } from "@/features/admin-catalog/load";
import { AgreementsPanel } from "@/features/admin-finance/AgreementsPanel";
import { Link } from "@/i18n/navigation";
import { requireCatalogEditor } from "@/lib/auth/require";

export default async function EditArtistPage({ params }: PageProps<"/[locale]/admin/artists/[id]">) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  await requireCatalogEditor(locale, `/admin/artists/${id}`);
  if (!isUuid(id)) notFound();
  const artist = await loadAdmin<AdminArtist>(`/admin/artists/${id}`);
  const t = await getTranslations("admin.artists");
  const tc = await getTranslations("common");
  return (
    <>
      <Link href="/admin/artists" className="text-sm text-muted hover:text-primary">
        {tc("back")}
      </Link>
      <div className="mt-2 mb-10 flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="text-3xl font-semibold text-primary">{artist.name}</h1>
        {artist.status === "active" && artist.slug ? (
          <Link href={`/artists/${artist.slug}`} className="text-sm text-primary underline hover:text-secondary">
            {t("viewPublic")}
          </Link>
        ) : null}
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-12 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <ArtistForm artist={artist} />
        <aside className="flex flex-col gap-10">
          <AgreementsPanel artistId={artist.id} artistName={artist.name} />
          <ArtistPhoto artist={artist} />
          <ArtistDelete id={artist.id} name={artist.name} />
        </aside>
      </div>
    </>
  );
}
