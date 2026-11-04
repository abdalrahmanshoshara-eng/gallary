"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Link } from "@/i18n/navigation";
import { pageCount } from "@/lib/catalog/types";

import { artworksKey, listArtworks } from "./api";

const inputClass = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";
type Status = "draft" | "published" | "hidden";

export function ArtworksTable() {
  const t = useTranslations("admin.artworks");
  const tc = useTranslations("common");
  const format = useFormatter();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [archived, setArchived] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const params = { search: debounced, status, archived, page };
  const artworks = useQuery({
    queryKey: artworksKey(params),
    queryFn: () => listArtworks(params),
    placeholderData: keepPreviousData,
  });
  const totalPages = artworks.data ? pageCount(artworks.data.count) : 1;
  const filter = (setter: (v: string) => void) => (e: { target: { value: string } }) => {
    setter(e.target.value);
    setPage(1);
  };

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
            onChange={filter(setSearch)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("filterStatus")}
          <select className={inputClass} value={status} onChange={filter(setStatus)}>
            <option value="">{tc("all")}</option>
            {(["draft", "published", "hidden"] as const).map((s) => (
              <option key={s} value={s}>
                {t(`status.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("archiveFilter")}
          <select className={inputClass} value={archived} onChange={filter(setArchived)}>
            <option value="">{tc("all")}</option>
            <option value="false">{t("notArchived")}</option>
            <option value="true">{t("archived")}</option>
          </select>
        </label>
      </div>

      {artworks.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {artworks.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {artworks.data && artworks.data.results.length === 0 ? <p className="text-muted">{t("empty")}</p> : null}
      {artworks.data && artworks.data.results.length > 0 ? (
        <ul className="divide-y divide-border/60 border-y border-border/60">
          {artworks.data.results.map((artwork) => (
            <li key={artwork.id} className="flex items-center gap-4 py-4">
              <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-control)] bg-surface text-xs text-muted">
                {artwork.primary_image ? (
                  <ResponsiveImage image={artwork.primary_image.image} alt="" sizes="4rem" />
                ) : (
                  t("noImage")
                )}
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  href={`/admin/artworks/${artwork.id}`}
                  className="font-medium text-primary hover:text-secondary"
                >
                  {artwork.title}
                </Link>
                <p className="truncate text-sm text-muted">
                  {[artwork.creator_name, artwork.category.name].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1 text-xs">
                <span className={artwork.publication_status === "published" ? "text-olive" : "text-primary"}>
                  {t(`status.${(artwork.publication_status ?? "draft") as Status}`)}
                </span>
                {artwork.is_archived ? <span className="text-secondary">{t("archived")}</span> : null}
                <span className="text-muted">
                  {format.dateTime(new Date(artwork.updated_at), { dateStyle: "medium" })}
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
