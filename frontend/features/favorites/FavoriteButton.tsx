"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";

import { addFavorite, favoriteIdsKey, listFavoriteIds, removeFavorite } from "./api";

/**
 * Heart toggle. Public pages are cached for everyone, so the favourite state is fetched in
 * the browser (one request per page for all hearts) and updated optimistically.
 */
export function FavoriteButton({ artworkId, title, size = "md" }: { artworkId: string; title: string; size?: "sm" | "md" }) {
  const t = useTranslations("favorites");
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const ids = useQuery({
    queryKey: favoriteIdsKey,
    queryFn: listFavoriteIds,
    enabled: Boolean(user && !user.is_staff),
    staleTime: 60_000,
  });
  const active = Boolean(ids.data?.ids.includes(artworkId));

  const toggle = useMutation({
    mutationFn: (next: boolean) => (next ? addFavorite(artworkId) : removeFavorite(artworkId)),
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: favoriteIdsKey });
      const previous = queryClient.getQueryData<{ ids: string[] }>(favoriteIdsKey);
      const current = previous?.ids ?? [];
      queryClient.setQueryData(favoriteIdsKey, {
        ids: next ? [...current, artworkId] : current.filter((id) => id !== artworkId),
      });
      return { previous };
    },
    onError: (_error, _next, context) => queryClient.setQueryData(favoriteIdsKey, context?.previous),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: favoriteIdsKey });
      void queryClient.invalidateQueries({ queryKey: ["favorites", "list"] });
    },
  });

  const box = size === "sm" ? "size-10" : "size-11";
  const icon = (
    <svg viewBox="0 0 24 24" aria-hidden className="size-5" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.6}>
      <path d="M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.4 4.5 7 4.5c2 0 3.4 1.1 5 3 1.6-1.9 3-3 5-3 3.6 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z" />
    </svg>
  );
  const className = `inline-flex ${box} items-center justify-center rounded-full border border-border bg-white/90 text-primary transition-colors duration-300 ease-calm hover:border-secondary`;

  if (user?.is_staff) return null; // favourites are a customer feature (PRD §8)
  if (!user) {
    return (
      <Link href={{ pathname: "/login" }} className={className} aria-label={t("loginToSave")} title={t("loginToSave")}>
        {icon}
      </Link>
    );
  }
  const label = active ? t("remove") : t("add");
  return (
    <button
      type="button"
      className={className}
      aria-pressed={active}
      aria-label={`${label}: ${title}`}
      title={label}
      disabled={toggle.isPending || ids.isPending}
      onClick={() => toggle.mutate(!active)}
    >
      {icon}
    </button>
  );
}
