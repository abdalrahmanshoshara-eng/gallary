import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtistCard } from "@/components/art/ArtistCard";
import { AuctionCard, type AuctionCardData } from "@/components/art/AuctionCard";
import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { Container } from "@/components/ui/Container";
import { HeroCarousel } from "@/features/home/HeroCarousel";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import type { Schema } from "@/lib/api/types";
import type { ArtistPublic, ArtworkCardData, CategoryNode, Page } from "@/lib/catalog/types";

const PILLARS = ["curated", "auctions", "archive"] as const;
type Home = Schema<"Home">;

// Refreshed from the API at most once a minute (ISR); the page stays static between refreshes.
export const revalidate = 60;

function SectionHeader({ id, title, href, more }: { id: string; title: string; href: string; more: string }) {
  return (
    <div className="mb-10 flex items-end justify-between gap-4">
      <h2 id={id} className="text-2xl font-semibold text-primary">
        {title}
      </h2>
      <Link href={href as "/"} className="text-sm text-secondary hover:underline">
        {more}
      </Link>
    </div>
  );
}

/**
 * Home (F-CMS-04): managed banners, live (else upcoming) auctions, curated works, categories,
 * latest works and featured artists. A section without content is not rendered.
 */
export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const safe = <T,>(p: Promise<T>) => p.catch(() => null);
  const [home, live, upcoming, categories, latest, artists] = await Promise.all([
    safe(publicApiGet<Home>("/home")),
    safe(publicApiGet<Page<AuctionCardData>>("/auctions", { status: "live" }, 30)),
    safe(publicApiGet<Page<AuctionCardData>>("/auctions", { status: "upcoming" }, 30)),
    safe(publicApiGet<CategoryNode[]>("/catalog/categories", undefined, 300)),
    safe(publicApiGet<Page<ArtworkCardData>>("/artworks")),
    safe(publicApiGet<Page<ArtistPublic>>("/artists", { featured: "true" })),
  ]);
  const auctionWindow = live?.results.length ? "live" : upcoming?.results.length ? "upcoming" : null;
  const auctions = (auctionWindow === "live" ? live : upcoming)?.results.slice(0, 4) ?? [];
  const featured = (home?.featured ?? []) as ArtworkCardData[];
  const featuredIds = new Set(featured.map((a) => a.id));

  return (
    <>
      {home && home.banners.length ? (
        <HeroCarousel banners={home.banners} />
      ) : (
        <section className="py-24 md:py-36">
          <Container className="max-w-3xl text-center">
            <p className="mb-6 text-sm tracking-wide text-secondary">{t("eyebrow")}</p>
            <h1 className="text-3xl font-semibold text-primary md:text-5xl">{t("title")}</h1>
            <p className="mx-auto mt-8 max-w-2xl text-lg text-muted">{t("intro")}</p>
          </Container>
        </section>
      )}

      {auctionWindow ? (
        <section aria-labelledby="home-auctions" className="border-t border-border/50 py-20">
          <Container>
            <SectionHeader
              id="home-auctions"
              title={auctionWindow === "live" ? t("auctionsLive") : t("auctionsUpcoming")}
              href={auctionWindow === "live" ? "/auctions" : "/auctions?status=upcoming"}
              more={t("auctionsMore")}
            />
            <div className="grid grid-cols-1 gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-4">
              {auctions.map((auction) => (
                <AuctionCard key={auction.id} auction={auction} window={auctionWindow} />
              ))}
            </div>
          </Container>
        </section>
      ) : null}

      {featured.length ? (
        <section aria-labelledby="home-featured" className="border-t border-border/50 py-20">
          <Container>
            <SectionHeader id="home-featured" title={t("featuredTitle")} href="/artworks" more={t("featuredMore")} />
            <ArtworkGrid artworks={featured.slice(0, 8)} emptyText="" />
          </Container>
        </section>
      ) : null}

      {categories && categories.length ? (
        <section aria-labelledby="home-categories" className="border-t border-border/50 py-16">
          <Container>
            <h2 id="home-categories" className="mb-8 text-2xl font-semibold text-primary">
              {t("categoriesTitle")}
            </h2>
            <ul className="flex flex-wrap gap-3">
              {categories.map((category) => (
                <li key={category.slug}>
                  <Link
                    href={`/artworks?category=${category.slug}`}
                    className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm text-text transition-colors duration-300 ease-calm hover:border-secondary hover:text-primary"
                  >
                    {category.name}
                  </Link>
                </li>
              ))}
            </ul>
          </Container>
        </section>
      ) : null}

      {latest && latest.results.length > 0 ? (
        <section aria-labelledby="latest" className="border-t border-border/50 py-20">
          <Container>
            <SectionHeader id="latest" title={t("latestTitle")} href="/artworks" more={t("latestMore")} />
            <ArtworkGrid artworks={latest.results.filter((a) => !featuredIds.has(a.id)).slice(0, 8)} emptyText="" />
          </Container>
        </section>
      ) : null}

      {artists && artists.results.length > 0 ? (
        <section aria-labelledby="featured" className="border-t border-border/50 py-20">
          <Container>
            <SectionHeader id="featured" title={t("featuredArtists")} href="/artists" more={t("artistsMore")} />
            <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-3">
              {artists.results.slice(0, 6).map((artist) => (
                <ArtistCard key={artist.id} artist={artist} />
              ))}
            </div>
          </Container>
        </section>
      ) : null}

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
          <p className="md:col-span-3">
            <Link href="/about" className="text-sm text-secondary hover:underline">
              {t("aboutMore")}
            </Link>
          </p>
        </Container>
      </section>
    </>
  );
}
