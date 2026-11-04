import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import type { ArtistPublic } from "@/lib/catalog/types";

import { ResponsiveImage } from "./ResponsiveImage";

export async function ArtistCard({ artist }: { artist: ArtistPublic }) {
  const t = await getTranslations("catalog");
  return (
    <article>
      <Link href={`/artists/${artist.slug}`} className="group flex items-center gap-5">
        <div className="flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface">
          {artist.photo ? (
            <ResponsiveImage image={artist.photo} alt={artist.name} sizes="96px" className="object-cover" />
          ) : (
            <span aria-hidden className="font-heading text-2xl text-secondary">
              {artist.name.charAt(0)}
            </span>
          )}
        </div>
        <div>
          <h3 className="font-heading text-lg text-primary group-hover:text-secondary">{artist.name}</h3>
          <p className="text-sm text-muted">
            {[artist.city, t("artworkCount", { count: artist.artwork_count })].filter(Boolean).join(" · ")}
          </p>
        </div>
      </Link>
    </article>
  );
}
