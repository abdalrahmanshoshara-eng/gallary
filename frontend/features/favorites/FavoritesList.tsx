"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Link } from "@/i18n/navigation";
import { apiFetch } from "@/lib/api/client";
import type { ArtworkCardData, Page } from "@/lib/catalog/types";
import { formatUsd } from "@/lib/formatters/money";

import { FavoriteButton } from "./FavoriteButton";

const listFavorites = () => apiFetch<Page<ArtworkCardData>>("/favorites?page_size=100");

export function FavoritesList() {
  const t = useTranslations("favorites");
  const tc = useTranslations("common");
  const to = useTranslations("catalog.offer");
  const favorites = useQuery({ queryKey: ["favorites", "list"], queryFn: listFavorites });

  if (favorites.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (favorites.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  if (favorites.data.results.length === 0) {
    return (
      <p className="text-muted">
        {t("empty")}{" "}
        <Link href="/artworks" className="text-secondary underline">
          {t("browse")}
        </Link>
      </p>
    );
  }
  return (
    <ul className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
      {favorites.data.results.map((artwork) => (
        <li key={artwork.id} className="relative">
          <div className="absolute end-3 top-3 z-10">
            <FavoriteButton artworkId={artwork.id} title={artwork.title} size="sm" />
          </div>
          <Link href={`/artworks/${artwork.slug}`} className="group block">
            <div className="flex aspect-[4/5] items-center justify-center overflow-hidden rounded-[var(--radius-card)] bg-surface/60 p-4">
              {artwork.primary_image ? (
                <ResponsiveImage image={artwork.primary_image.image} alt={artwork.title} sizes="(min-width: 1024px) 30vw, 90vw" />
              ) : null}
            </div>
            <h2 className="mt-3 font-heading text-lg text-primary group-hover:text-secondary">{artwork.title}</h2>
          </Link>
          <p className="text-sm text-muted">{artwork.artist?.name ?? artwork.creator_name}</p>
          {artwork.offer?.purchasable && artwork.offer.price_usd ? (
            <p className="mt-1 font-medium text-primary">
              <bdi dir="ltr">{formatUsd(artwork.offer.price_usd)}</bdi>
            </p>
          ) : artwork.offer ? (
            <p className="mt-1 text-sm text-muted">{to(`status.${(artwork.offer.unavailable_reason ?? "not_active") as "sold_out"}`)}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
