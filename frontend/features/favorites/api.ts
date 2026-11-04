import { apiFetch } from "@/lib/api/client";

export const favoriteIdsKey = ["favorites", "ids"] as const;
export const listFavoriteIds = () => apiFetch<{ ids: string[] }>("/favorites/ids");
export const addFavorite = (artworkId: string) => apiFetch<void>(`/favorites/${artworkId}`, { method: "PUT" });
export const removeFavorite = (artworkId: string) => apiFetch<void>(`/favorites/${artworkId}`, { method: "DELETE" });
