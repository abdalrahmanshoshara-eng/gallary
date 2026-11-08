"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { listArtworks } from "@/features/admin-catalog/api";
import { errorText } from "@/lib/forms";

import { addFeatured, featuredKey, listFeatured, moveFeatured, removeFeatured, type AdminFeatured } from "./api";
import { MoveButtons } from "./ContentTabs";

const MAX = 12;

/** Curated works for the home page (F-CMS-03), in the order shown to visitors. */
export function FeaturedManager() {
  const t = useTranslations("admin.content.featured");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const featured = useQuery({ queryKey: featuredKey, queryFn: listFeatured });
  const results = useQuery({
    queryKey: ["admin", "content", "featured-search", debounced],
    queryFn: () => listArtworks({ search: debounced, status: "published" }),
    enabled: debounced.length > 0,
    placeholderData: keepPreviousData,
  });
  const act = useMutation({
    mutationFn: (fn: () => Promise<AdminFeatured[]>) => fn(),
    onSuccess: (rows) => queryClient.setQueryData(featuredKey, rows),
  });

  if (featured.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (featured.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  const rows = featured.data;
  const chosen = new Set(rows.map((r) => r.artwork_id));
  const full = rows.length >= MAX;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="text-sm text-muted">{t("intro", { max: MAX })}</p>
        <p className="mt-1 text-xs text-muted">{t("artistsHint")}</p>
      </div>
      {act.error ? <Alert tone="error">{errorText(act.error)}</Alert> : null}

      <ol className="flex flex-col gap-3">
        {rows.length === 0 ? <li className="text-muted">{t("empty")}</li> : null}
        {rows.map((item, index) => (
          <li key={item.artwork_id} className={`flex items-center gap-4 rounded-[var(--radius-card)] border p-3 ${item.is_public ? "border-border/60" : "border-primary/40 bg-primary/5"}`}>
            <span className="w-6 text-center text-sm text-muted tabular-nums">{index + 1}</span>
            <span className="size-14 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
              {item.image ? <ResponsiveImage image={item.image.image} alt="" sizes="3.5rem" /> : null}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-primary">{item.title}</span>
              <span className="block truncate text-xs text-muted">{item.creator_name}</span>
              {!item.is_public ? <span className="block text-xs font-medium text-primary">{t("notPublic")}</span> : null}
            </span>
            <MoveButtons
              first={index === 0}
              last={index === rows.length - 1}
              busy={act.isPending}
              upLabel={t("up", { title: item.title })}
              downLabel={t("down", { title: item.title })}
              onMove={(d) => act.mutate(() => moveFeatured(item.artwork_id, d))}
            />
            <Button variant="ghost" className="min-h-9 px-3" onClick={() => act.mutate(() => removeFeatured(item.artwork_id))}>
              {t("remove")}
            </Button>
          </li>
        ))}
      </ol>

      <section className="flex flex-col gap-3 border-t border-border/60 pt-6">
        {full ? <Alert tone="info">{t("full", { max: MAX })}</Alert> : null}
        <label className="flex flex-col gap-1 text-sm">
          {tc("search")}
          <input
            type="search"
            className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
            placeholder={t("search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            disabled={full}
          />
        </label>
        {debounced && results.data?.results.length === 0 ? <p className="text-sm text-muted">{t("noResults")}</p> : null}
        {debounced && results.data?.results.length ? (
          <ul className="divide-y divide-border/50 rounded-[var(--radius-card)] border border-border/60">
            {results.data.results.map((artwork) => (
              <li key={artwork.id} className="flex items-center gap-3 p-3">
                <span className="size-12 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
                  {artwork.primary_image ? <ResponsiveImage image={artwork.primary_image.image} alt="" sizes="3rem" /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-primary">{artwork.title}</span>
                  <span className="block truncate text-xs text-muted">{artwork.creator_name}</span>
                </span>
                {chosen.has(artwork.id) ? (
                  <span className="text-xs text-olive">{t("already")}</span>
                ) : (
                  <Button variant="secondary" className="min-h-9 px-4" disabled={full || act.isPending} onClick={() => act.mutate(() => addFeatured(artwork.id))}>
                    {t("add")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
