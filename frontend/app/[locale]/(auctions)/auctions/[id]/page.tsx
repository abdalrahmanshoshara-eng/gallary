import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { AuctionLive } from "@/features/auctions/AuctionLive";
import type { AuctionDetail } from "@/features/auctions/api";
import { durationText, percentText } from "@/features/auctions/format";
import { Gallery } from "@/features/catalog/Gallery";
import { Link } from "@/i18n/navigation";
import { publicApiGetOrNull } from "@/lib/api/public";

type Props = PageProps<"/[locale]/auctions/[id]">;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function load(id: string) {
  if (!UUID.test(id)) return null;
  // Static parts only (title, images, rules); the live state comes from the stream.
  return publicApiGetOrNull<AuctionDetail>(`/auctions/${id}`, 30);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const auction = await load(id);
  if (!auction) return {};
  const image = auction.images[0]?.image.variants.at(-1);
  return {
    title: auction.title,
    description: auction.description.slice(0, 160) || auction.title,
    openGraph: image ? { images: [{ url: image.url, width: image.width, height: image.height }] } : undefined,
  };
}

export default async function AuctionPage({ params }: Props) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const auction = await load(id);
  if (!auction) notFound();
  const t = await getTranslations("auctions");
  const minutes = (sec: number) => durationText(sec, t);
  const percent = percentText(auction.winner_deposit_percent);

  return (
    <Container className="py-12 md:py-16">
      <nav aria-label={t("title")} className="mb-6 text-sm">
        <Link href="/auctions" className="text-muted hover:text-secondary">
          {t("title")}
        </Link>
      </nav>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-12 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:gap-16">
        <div className="flex flex-col gap-10">
          <Gallery images={auction.images.map((img) => ({ id: img.id, alt: img.alt_text || auction.title, image: img.image }))} />
          {auction.description ? (
            <section aria-labelledby="about-work" className="hidden lg:block">
              <h2 id="about-work" className="mb-3 text-lg font-medium text-primary">
                {t("artwork")}
              </h2>
              <p className="whitespace-pre-line leading-8">{auction.description}</p>
            </section>
          ) : null}
        </div>

        <div className="flex flex-col gap-8">
          <header>
            <h1 className="text-3xl font-semibold text-primary md:text-4xl">{auction.title}</h1>
            <p className="mt-3 text-lg text-text">{auction.creator_name}</p>
          </header>

          <AuctionLive detail={auction} />

          {auction.description ? (
            <section aria-labelledby="about-work-sm" className="lg:hidden">
              <h2 id="about-work-sm" className="mb-3 text-lg font-medium text-primary">
                {t("artwork")}
              </h2>
              <p className="whitespace-pre-line leading-8">{auction.description}</p>
            </section>
          ) : null}

          <section aria-labelledby="auction-terms" className="rounded-[var(--radius-card)] border border-border/60 p-5">
            <h2 id="auction-terms" className="text-lg font-medium text-primary">
              {t("terms.title")}
            </h2>
            <ul className="mt-3 flex list-disc flex-col gap-2 ps-5 text-sm leading-7">
              <li>{t("terms.deposit", { percent })}</li>
              <li>{t("terms.window", { window: minutes(auction.winner_payment_window_sec) })}</li>
              <li>
                {auction.max_extensions > 0 && auction.extension_duration_sec > 0
                  ? t("terms.extension", {
                      window: minutes(auction.extension_window_sec),
                      duration: minutes(auction.extension_duration_sec),
                      max: auction.max_extensions,
                    })
                  : t("terms.noExtension")}
              </li>
              <li>{t(`terms.nonPayment.${auction.non_payment_policy}`)}</li>
              {auction.reserve_met !== null ? <li>{t("terms.reserve")}</li> : null}
            </ul>
            {auction.terms ? <p className="mt-4 whitespace-pre-line text-sm leading-7 text-text">{auction.terms}</p> : null}
          </section>

          <p className="text-sm">
            <Link href={`/artworks/${auction.artwork_slug}`} className="text-primary underline-offset-4 hover:underline">
              {t("viewArtwork")}
            </Link>
          </p>
        </div>
      </div>
    </Container>
  );
}
