"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/navigation";

import { artistsKey, listArtists } from "./api";

const inputClass = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";

export function ArtistsTable() {
  const t = useTranslations("admin.artists");
  const tc = useTranslations("common");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = { search: debounced, status, page };
  const artists = useQuery({ queryKey: artistsKey(params), queryFn: () => listArtists(params), placeholderData: keepPreviousData });
  const totalPages = artists.data ? Math.max(1, Math.ceil(artists.data.count / 25)) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex min-w-64 flex-1 flex-col gap-1 text-sm">
          {tc("search")}
          <input
            type="search"
            className={inputClass}
            placeholder={t("searchPlaceholder")}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {tc("status")}
          <select
            className={inputClass}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{tc("all")}</option>
            <option value="active">{t("statusActive")}</option>
            <option value="hidden">{t("statusHidden")}</option>
          </select>
        </label>
      </div>
      {artists.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {artists.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {artists.data && artists.data.results.length === 0 ? <p className="text-muted">{t("empty")}</p> : null}
      {artists.data && artists.data.results.length > 0 ? (
        <ul className="divide-y divide-border/60 border-y border-border/60">
          {artists.data.results.map((artist) => (
            <li key={artist.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
              <div>
                <Link href={`/admin/artists/${artist.id}`} className="font-medium text-primary hover:text-secondary">
                  {artist.name}
                </Link>
                <p className="text-sm text-muted">
                  {[artist.city, t("artworks", { count: artist.artwork_count })].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                {artist.is_featured ? <span className="text-secondary">{t("featured")}</span> : null}
                <span className={artist.status === "hidden" ? "text-primary" : "text-olive"}>
                  {artist.status === "hidden" ? t("statusHidden") : t("statusActive")}
                </span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      {totalPages > 1 ? (
        <div className="flex items-center gap-4 text-sm">
          <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {tc("previous")}
          </Button>
          <span>{tc("pageOf", { page, total: totalPages })}</span>
          <Button variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            {tc("next")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
