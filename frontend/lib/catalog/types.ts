import type { Schema } from "@/lib/api/types";

export type PublicImage = Schema<"PublicImage">;
export type ArtworkCardData = Schema<"PublicArtworkCard">;
export type ArtworkDetail = Schema<"PublicArtworkDetail">;
export type ArtistPublic = Schema<"PublicArtist">;
export type CategoryNode = Schema<"PublicCategory">;

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const PAGE_SIZE = 25;

export function pageCount(count: number, size = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(count / size));
}

export function parsePage(value: string | string[] | undefined): number {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(n) && n > 0 ? n : 1;
}
