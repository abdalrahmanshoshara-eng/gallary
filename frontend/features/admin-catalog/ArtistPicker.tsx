"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";

import { artistKey, artistsKey, getArtist, listArtists, type AdminArtist } from "./api";

type Props = {
  label: string;
  emptyLabel: string;
  value: string;
  onChange: (value: string) => void;
  searchPlaceholder: string;
  hiddenLabel: string;
};

/**
 * Server-searched artist select: scales past one page of artists, and always keeps the
 * currently selected artist as an option even when it is not in the search results.
 */
export function ArtistPicker({ label, emptyLabel, value, onChange, searchPlaceholder, hiddenLabel }: Props) {
  const id = useId();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const params = { search: debounced, page_size: 50 };
  const results = useQuery({
    queryKey: artistsKey(params),
    queryFn: () => listArtists(params),
    placeholderData: keepPreviousData,
  });
  const listed = results.data?.results ?? [];
  const selected = useQuery({
    queryKey: artistKey(value),
    queryFn: () => getArtist(value),
    enabled: Boolean(value) && !listed.some((a) => a.id === value),
  });
  const options: AdminArtist[] =
    selected.data && !listed.some((a) => a.id === selected.data.id) ? [selected.data, ...listed] : listed;

  return (
    <div className="flex flex-col gap-2 text-sm">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          aria-label={searchPlaceholder}
          placeholder={searchPlaceholder}
          className="min-h-11 min-w-40 flex-1 rounded-[var(--radius-control)] border border-border bg-white px-3"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          id={id}
          className="min-h-11 min-w-48 flex-1 rounded-[var(--radius-control)] border border-border bg-white px-3"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">{emptyLabel}</option>
          {options.map((artist) => (
            <option key={artist.id} value={artist.id}>
              {artist.name}
              {/* City and birth year tell apart artists who share a name. */}
              {artist.city || artist.birth_year
                ? ` — ${[artist.city, artist.birth_year].filter(Boolean).join("، ")}`
                : ""}
              {artist.status === "hidden" ? ` (${hiddenLabel})` : ""}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
