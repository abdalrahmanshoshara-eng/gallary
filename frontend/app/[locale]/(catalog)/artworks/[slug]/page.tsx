import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Gallery } from "@/features/catalog/Gallery";
import { Link } from "@/i18n/navigation";
import { publicApiGetOrNull } from "@/lib/api/public";
import type { ArtworkDetail } from "@/lib/catalog/types";

type Props = PageProps<"/[locale]/artworks/[slug]">;

async function load(slug: string) {
  return publicApiGetOrNull<ArtworkDetail>(`/artworks/${encodeURIComponent(decodeURIComponent(slug))}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const artwork = await load(slug);
  if (!artwork) return {};
  const image = artwork.images[0]?.image.variants.at(-1);
  const by = artwork.artist?.name ?? artwork.creator_name;
  return {
    title: artwork.title,
    description: artwork.description.slice(0, 160) || `${artwork.title} — ${by}`,
    openGraph: image ? { images: [{ url: image.url, width: image.width, height: image.height }] } : undefined,
  };
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-4 border-b border-border/40 py-3 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="col-span-2">{children}</dd>
    </div>
  );
}

export default async function ArtworkPage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const artwork = await load(slug);
  if (!artwork) notFound();
  const t = await getTranslations("catalog");
  const d = artwork.dimensions;
  const size = [d.height_cm, d.width_cm, d.depth_cm].filter(Boolean).map((v) => Number(v).toString());
  const join = (items: { name: string }[]) => items.map((i) => i.name).join("، ");

  return (
    <Container className="py-12 md:py-16">
      <div className="grid gap-12 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-16">
        <Gallery
          images={artwork.images.map((img) => ({ id: img.id, alt: img.alt_text || artwork.title, image: img.image }))}
        />

        <div>
          <p className="text-sm text-secondary">
            <Link href={`/artworks?category=${artwork.category.parent?.slug ?? artwork.category.slug}`}>
              {artwork.category.parent ? `${artwork.category.parent.name} · ` : ""}
              {artwork.category.name}
            </Link>
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-primary md:text-4xl">{artwork.title}</h1>
          <p className="mt-3 text-lg">
            {artwork.artist ? (
              <Link href={`/artists/${artwork.artist.slug}`} className="text-text hover:text-secondary">
                {artwork.artist.name}
              </Link>
            ) : (
              artwork.creator_name
            )}
            {artwork.year_created ? <span className="text-muted"> · {artwork.year_created}</span> : null}
          </p>

          <div className="mt-8 rounded-[var(--radius-card)] border border-border/60 bg-white/50 p-5 text-sm">
            {artwork.is_archived ? (
              <p className="text-olive">{t("archivedNotice")}</p>
            ) : (
              <p className="text-muted">{t("notForSale")}</p>
            )}
          </div>

          {artwork.description ? (
            <div className="mt-8 whitespace-pre-line leading-8 text-text">{artwork.description}</div>
          ) : null}

          <h2 className="mt-12 mb-2 text-lg font-medium text-primary">{t("details.title")}</h2>
          <dl>
            {artwork.artist ? (
              <Row label={t("details.artist")}>{artwork.artist.name}</Row>
            ) : (
              <Row label={t("details.creator")}>{artwork.creator_name}</Row>
            )}
            {artwork.executor ? <Row label={t("details.executor")}>{artwork.executor.name}</Row> : null}
            {artwork.owner_name ? <Row label={t("details.owner")}>{artwork.owner_name}</Row> : null}
            {artwork.rights_holder ? <Row label={t("details.rightsHolder")}>{artwork.rights_holder}</Row> : null}
            <Row label={t("details.category")}>{artwork.category.name}</Row>
            {artwork.techniques.length ? <Row label={t("details.techniques")}>{join(artwork.techniques)}</Row> : null}
            {artwork.materials.length ? <Row label={t("details.materials")}>{join(artwork.materials)}</Row> : null}
            {size.length ? (
              <Row label={t("details.dimensions")}>
                <bdi dir="ltr">{t("dimensionsValue", { value: size.join(" × ") })}</bdi>
              </Row>
            ) : null}
            {d.weight_kg ? <Row label={t("details.weight")}>{t("weightValue", { value: Number(d.weight_kg) })}</Row> : null}
            {artwork.year_created ? <Row label={t("details.year")}>{artwork.year_created}</Row> : null}
            {artwork.tags.length ? <Row label={t("details.tags")}>{join(artwork.tags)}</Row> : null}
          </dl>
        </div>
      </div>
    </Container>
  );
}
