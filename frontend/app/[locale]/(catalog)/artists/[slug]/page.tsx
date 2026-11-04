import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Container } from "@/components/ui/Container";
import { publicApiGet, publicApiGetOrNull } from "@/lib/api/public";
import type { ArtistPublic, ArtworkCardData, Page } from "@/lib/catalog/types";

type Props = PageProps<"/[locale]/artists/[slug]">;

const load = (slug: string) =>
  publicApiGetOrNull<ArtistPublic>(`/artists/${encodeURIComponent(decodeURIComponent(slug))}`);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const artist = await load((await params).slug);
  return artist ? { title: artist.name, description: artist.biography.slice(0, 160) || undefined } : {};
}

export default async function ArtistPage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const artist = await load(slug);
  if (!artist) notFound();
  const t = await getTranslations("catalog");
  const [available, archived] = await Promise.all([
    publicApiGet<Page<ArtworkCardData>>("/artworks", { artist: artist.slug }),
    publicApiGet<Page<ArtworkCardData>>("/archive", { artist: artist.slug }),
  ]);

  return (
    <Container className="py-16">
      <header className="flex flex-col gap-8 md:flex-row md:items-center">
        {artist.photo ? (
          <div className="size-40 shrink-0 overflow-hidden rounded-full bg-surface">
            <ResponsiveImage image={artist.photo} alt={artist.name} sizes="160px" className="object-cover" priority />
          </div>
        ) : null}
        <div className="max-w-2xl">
          {artist.is_featured ? <p className="text-sm text-secondary">{t("featured")}</p> : null}
          <h1 className="mt-1 text-3xl font-semibold text-primary md:text-4xl">{artist.name}</h1>
          <p className="mt-2 text-muted">
            {[artist.city, artist.birth_year ? t("born", { year: artist.birth_year }) : null].filter(Boolean).join(" · ")}
          </p>
          {artist.biography ? <p className="mt-6 whitespace-pre-line leading-8">{artist.biography}</p> : null}
        </div>
      </header>

      <section className="mt-16" aria-labelledby="available">
        <h2 id="available" className="mb-8 text-xl font-medium text-primary">
          {t("availableWorks")}
        </h2>
        <ArtworkGrid artworks={available.results} emptyText={t("noAvailableWorks")} />
      </section>

      {archived.results.length ? (
        <section className="mt-20" aria-labelledby="archived">
          <h2 id="archived" className="mb-8 text-xl font-medium text-primary">
            {t("archivedWorks")}
          </h2>
          <ArtworkGrid artworks={archived.results} emptyText="" />
        </section>
      ) : null}
    </Container>
  );
}
