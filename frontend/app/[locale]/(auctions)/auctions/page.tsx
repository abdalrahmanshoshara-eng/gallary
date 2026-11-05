import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuctionCard, type AuctionCardData, type AuctionWindow } from "@/components/art/AuctionCard";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { Pagination } from "@/components/ui/Pagination";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import { pageCount, parsePage, type Page } from "@/lib/catalog/types";

const WINDOWS: AuctionWindow[] = ["live", "upcoming", "ended"];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auctions");
  return { title: t("title"), description: t("intro") };
}

export default async function AuctionsPage({ params, searchParams }: PageProps<"/[locale]/auctions">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const query = await searchParams;
  const t = await getTranslations("auctions");
  const requested = typeof query.status === "string" ? query.status : "live";
  const window: AuctionWindow = WINDOWS.includes(requested as AuctionWindow) ? (requested as AuctionWindow) : "live";
  const page = parsePage(query.page);
  // Short revalidation: lists classify by time; the auction page itself is live.
  const auctions = await publicApiGet<Page<AuctionCardData>>(
    "/auctions",
    { status: window, page: page > 1 ? page : undefined },
    15,
  );

  const tab = (active: boolean) =>
    [
      "inline-flex min-h-11 items-center rounded-full border px-5 text-sm transition-colors duration-300 ease-calm",
      active ? "border-primary bg-primary text-on-primary" : "border-border text-text hover:border-secondary",
    ].join(" ");

  return (
    <Container className="py-16">
      <header className="max-w-2xl">
        <h1 className="text-4xl font-semibold text-primary">{t("title")}</h1>
        <p className="mt-4 leading-8 text-muted">{t("intro")}</p>
      </header>

      <nav aria-label={t("tabsLabel")} className="mt-10">
        <ul className="flex flex-wrap gap-3">
          {WINDOWS.map((w) => (
            <li key={w}>
              <Link
                href={w === "live" ? "/auctions" : `/auctions?status=${w}`}
                aria-current={w === window ? "page" : undefined}
                className={tab(w === window)}
              >
                {t(`tabs.${w}`)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-12">
        {auctions.results.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <Icon name="clock" className="size-12 text-secondary" />
            <p className="text-lg text-primary">{t(`empty.${window}`)}</p>
            <p className="max-w-sm text-sm text-muted">{t("emptyHint")}</p>
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              {window !== "upcoming" ? (
                <Link href="/auctions?status=upcoming" className={tab(false)}>
                  {t("browseUpcoming")}
                </Link>
              ) : null}
              <Link href="/artworks" className={tab(false)}>
                {t("browseArtworks")}
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {auctions.results.map((auction, index) => (
              <AuctionCard key={auction.id} auction={auction} window={window} priority={index < 4} />
            ))}
          </div>
        )}
      </div>

      <Pagination
        pathname="/auctions"
        page={page}
        totalPages={pageCount(auctions.count)}
        query={{ status: window === "live" ? undefined : window }}
      />

      <aside className="mt-20 flex flex-col items-start gap-4 rounded-[var(--radius-card)] border border-border/60 bg-white/50 p-6 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-medium text-primary">{t("sellCta.title")}</h2>
          <p className="mt-1 text-sm text-muted">{t("sellCta.body")}</p>
        </div>
        <Link
          href="/auction-requests/new"
          className="inline-flex min-h-11 shrink-0 items-center rounded-[var(--radius-control)] border border-secondary px-6 text-sm font-medium text-primary hover:bg-surface"
        >
          {t("sellCta.action")}
        </Link>
      </aside>
    </Container>
  );
}
