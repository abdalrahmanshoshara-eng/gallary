import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import type { ArtworkCardData } from "@/lib/catalog/types";

import { ResponsiveImage } from "./ResponsiveImage";

export async function ArtworkCard({ artwork, priority = false }: { artwork: ArtworkCardData; priority?: boolean }) {
  const t = await getTranslations("catalog");
  return (
    <article className="group">
      <Link href={`/artworks/${artwork.slug}`} className="block">
        <div className="flex aspect-[4/5] items-center justify-center overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-4 transition-colors duration-500 ease-calm group-hover:bg-surface">
          {artwork.primary_image ? (
            <ResponsiveImage
              image={artwork.primary_image.image}
              alt={artwork.primary_image.alt_text || artwork.title}
              sizes="(min-width: 1280px) 22vw, (min-width: 768px) 30vw, 90vw"
              priority={priority}
            />
          ) : (
            <span className="text-sm text-muted">{t("noImage")}</span>
          )}
        </div>
        <h3 className="mt-4 font-heading text-lg text-primary group-hover:text-secondary">{artwork.title}</h3>
      </Link>
      <p className="mt-1 text-sm text-muted">
        {artwork.artist ? (
          <Link href={`/artists/${artwork.artist.slug}`} className="hover:text-secondary">
            {artwork.artist.name}
          </Link>
        ) : (
          artwork.creator_name
        )}
        {artwork.year_created ? <span> · {artwork.year_created}</span> : null}
      </p>
      {artwork.is_archived ? <p className="mt-1 text-xs text-olive">{t("archivedBadge")}</p> : null}
    </article>
  );
}

export async function ArtworkGrid({ artworks, emptyText }: { artworks: ArtworkCardData[]; emptyText: string }) {
  if (artworks.length === 0) return <p className="py-16 text-center text-muted">{emptyText}</p>;
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {artworks.map((artwork, index) => (
        <ArtworkCard key={artwork.id} artwork={artwork} priority={index < 4} />
      ))}
    </div>
  );
}
