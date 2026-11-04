import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtistCard } from "@/components/art/ArtistCard";
import { Container } from "@/components/ui/Container";
import { Pagination } from "@/components/ui/Pagination";
import { publicApiGet } from "@/lib/api/public";
import { pageCount, parsePage, type ArtistPublic, type Page } from "@/lib/catalog/types";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("catalog");
  return { title: t("artistsTitle"), description: t("artistsIntro") };
}

export default async function ArtistsPage({ params, searchParams }: PageProps<"/[locale]/artists">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const page = parsePage((await searchParams).page);
  const t = await getTranslations("catalog");
  const artists = await publicApiGet<Page<ArtistPublic>>("/artists", { page: page > 1 ? page : undefined });

  return (
    <Container className="py-16">
      <h1 className="text-3xl font-semibold text-primary md:text-4xl">{t("artistsTitle")}</h1>
      <p className="mt-4 text-muted">{t("artistsIntro")}</p>
      {artists.results.length ? (
        <div className="mt-12 grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
          {artists.results.map((artist) => (
            <ArtistCard key={artist.id} artist={artist} />
          ))}
        </div>
      ) : (
        <p className="py-16 text-center text-muted">{t("emptyArtists")}</p>
      )}
      <Pagination pathname="/artists" page={page} totalPages={pageCount(artists.count)} />
    </Container>
  );
}
