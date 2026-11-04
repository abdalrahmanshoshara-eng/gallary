import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtistCard } from "@/components/art/ArtistCard";
import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import type { ArtistPublic, ArtworkCardData, Page } from "@/lib/catalog/types";

const PILLARS = ["curated", "auctions", "archive"] as const;

// Refreshed from the API at most once a minute (ISR); the page stays static between refreshes.
export const revalidate = 60;

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  // Real data only: sections appear once the catalogue has content.
  const [latest, featured] = await Promise.all([
    publicApiGet<Page<ArtworkCardData>>("/artworks").catch(() => null),
    publicApiGet<Page<ArtistPublic>>("/artists", { featured: "true" }).catch(() => null),
  ]);

  return (
    <>
      <section className="py-24 md:py-36">
        <Container className="max-w-3xl text-center">
          <p className="mb-6 text-sm tracking-wide text-secondary">{t("eyebrow")}</p>
          <h1 className="text-3xl font-semibold text-primary md:text-5xl">{t("title")}</h1>
          <p className="mx-auto mt-8 max-w-2xl text-lg text-muted">{t("intro")}</p>
        </Container>
      </section>
      <section aria-labelledby="pillars" className="border-t border-border/50 py-20">
        <h2 id="pillars" className="sr-only">
          {t("eyebrow")}
        </h2>
        <Container className="grid gap-12 md:grid-cols-3">
          {PILLARS.map((key) => (
            <article key={key} className="text-start">
              <h3 className="text-xl font-medium text-primary">{t(`pillars.${key}.title`)}</h3>
              <p className="mt-3 text-muted">{t(`pillars.${key}.body`)}</p>
            </article>
          ))}
        </Container>
      </section>
      {latest && latest.results.length > 0 ? (
        <section aria-labelledby="latest" className="border-t border-border/50 py-20">
          <Container>
            <div className="mb-10 flex items-end justify-between gap-4">
              <h2 id="latest" className="text-2xl font-semibold text-primary">
                {t("latestTitle")}
              </h2>
              <Link href="/artworks" className="text-sm text-secondary hover:underline">
                {t("latestMore")}
              </Link>
            </div>
            <ArtworkGrid artworks={latest.results.slice(0, 8)} emptyText="" />
          </Container>
        </section>
      ) : null}
      {featured && featured.results.length > 0 ? (
        <section aria-labelledby="featured" className="border-t border-border/50 py-20">
          <Container>
            <div className="mb-10 flex items-end justify-between gap-4">
              <h2 id="featured" className="text-2xl font-semibold text-primary">
                {t("featuredArtists")}
              </h2>
              <Link href="/artists" className="text-sm text-secondary hover:underline">
                {t("artistsMore")}
              </Link>
            </div>
            <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
              {featured.results.slice(0, 6).map((artist) => (
                <ArtistCard key={artist.id} artist={artist} />
              ))}
            </div>
          </Container>
        </section>
      ) : null}
    </>
  );
}
