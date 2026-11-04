import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { Container } from "@/components/ui/Container";
import { Pagination } from "@/components/ui/Pagination";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import {
  pageCount,
  parsePage,
  type ArtistPublic,
  type ArtworkCardData,
  type CategoryNode,
  type Page,
} from "@/lib/catalog/types";

const ORDERINGS = ["newest", "oldest", "title", "year", "price_asc", "price_desc"] as const;
type Ordering = (typeof ORDERINGS)[number];
type Term = { name: string; slug: string };

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v.trim() : Array.isArray(v) ? (v[0] ?? "") : "");
const many = (v: string | string[] | undefined) => (Array.isArray(v) ? v : v ? [v] : []).filter(Boolean).slice(0, 10);
const money = (v: string) => (/^\d{1,9}(\.\d{1,2})?$/.test(v) ? v : "");
const pick = <T extends string>(v: string, allowed: readonly T[]) => (allowed.includes(v as T) ? (v as T) : "");

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("catalog");
  return { title: t("artworksTitle"), description: t("artworksIntro") };
}

export default async function ArtworksPage({ params, searchParams }: PageProps<"/[locale]/artworks">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const query = await searchParams;
  const t = await getTranslations("catalog");

  // Every value is validated before it is echoed into links or sent to the API.
  const filters = {
    q: one(query.q).slice(0, 100),
    category: one(query.category),
    artist: one(query.artist),
    price_min: money(one(query.price_min)),
    price_max: money(one(query.price_max)),
    availability: pick(one(query.availability), ["available", "unavailable"] as const),
    sale_mode: pick(one(query.sale_mode), ["fixed_price", "auction"] as const),
    material: many(query.material),
    technique: many(query.technique),
  };
  const ordering: Ordering = pick(one(query.ordering), ORDERINGS) || "newest";
  const page = parsePage(query.page);
  const kept = { ...filters, ordering: ordering === "newest" ? undefined : ordering };
  const filtered = Object.entries(filters).some(([, v]) => (Array.isArray(v) ? v.length : v));

  const [categories, artists, materials, techniques, artworks] = await Promise.all([
    publicApiGet<CategoryNode[]>("/catalog/categories", undefined, 300),
    publicApiGet<Page<ArtistPublic>>("/artists", { page_size: 100 }, 300),
    publicApiGet<Term[]>("/catalog/materials", undefined, 300),
    publicApiGet<Term[]>("/catalog/techniques", undefined, 300),
    publicApiGet<Page<ArtworkCardData>>("/artworks", { ...kept, page: page > 1 ? page : undefined }),
  ]);

  const chip = (active: boolean) =>
    [
      "rounded-full border px-4 py-1.5 text-sm transition-colors duration-300 ease-calm",
      active ? "border-primary bg-primary text-on-primary" : "border-border text-text hover:border-secondary",
    ].join(" ");
  const hrefWith = (changes: Record<string, string>) => {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...kept, ...changes })) {
      for (const item of Array.isArray(value) ? value : [value]) if (item) qs.append(key, item);
    }
    return qs.toString() ? `/artworks?${qs}` : "/artworks";
  };
  const field = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";
  const selected = categories.find((c) => c.slug === filters.category);

  return (
    <Container className="py-16">
      <header className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-primary md:text-4xl">{t("artworksTitle")}</h1>
        <p className="mt-4 text-muted">{t("artworksIntro")}</p>
      </header>

      <form method="get" action="/artworks" role="search" className="mt-10 flex flex-col gap-6">
        {filters.category ? <input type="hidden" name="category" value={filters.category} /> : null}
        <div className="flex gap-3">
          <label htmlFor="q" className="sr-only">
            {t("searchLabel")}
          </label>
          <input
            id="q"
            name="q"
            type="search"
            defaultValue={filters.q}
            placeholder={t("searchPlaceholder")}
            className={`${field} min-w-0 flex-1 text-base`}
          />
          <button type="submit" className="min-h-11 shrink-0 rounded-[var(--radius-control)] bg-primary px-6 text-on-primary">
            {t("search")}
          </button>
        </div>

        <details className="rounded-[var(--radius-card)] border border-border/60 p-4" open={filtered && !filters.q}>
          <summary className="cursor-pointer text-sm font-medium text-primary">{t("filters")}</summary>
          <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <label className="flex min-w-0 flex-col gap-1 text-sm">
              {t("artistFilter")}
              <select name="artist" defaultValue={filters.artist} className={field}>
                <option value="">{t("anyArtist")}</option>
                {artists.results.map((a) => (
                  <option key={a.slug} value={a.slug}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex gap-3">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                {t("priceMin")}
                <input name="price_min" inputMode="decimal" dir="ltr" defaultValue={filters.price_min} className={`${field} w-full min-w-0`} />
              </label>
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                {t("priceMax")}
                <input name="price_max" inputMode="decimal" dir="ltr" defaultValue={filters.price_max} className={`${field} w-full min-w-0`} />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-sm">
              {t("availability")}
              <select name="availability" defaultValue={filters.availability} className={field}>
                <option value="">{t("anyAvailability")}</option>
                <option value="available">{t("availableOnly")}</option>
                <option value="unavailable">{t("unavailableOnly")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              {t("saleMode")}
              <select name="sale_mode" defaultValue={filters.sale_mode} className={field}>
                <option value="">{t("anySaleMode")}</option>
                <option value="fixed_price">{t("fixedPrice")}</option>
                <option value="auction">{t("auction")}</option>
              </select>
            </label>
          </div>
          {([
            ["material", t("materials"), materials, filters.material],
            ["technique", t("techniques"), techniques, filters.technique],
          ] as const).map(([name, legend, terms, chosen]) => (
            <fieldset key={name} className="mt-6">
              <legend className="mb-2 text-sm font-medium">{legend}</legend>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {terms.map((term) => (
                  <label key={term.slug} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      name={name}
                      value={term.slug}
                      defaultChecked={chosen.includes(term.slug)}
                      className="size-4 accent-[var(--color-primary)]"
                    />
                    {term.name}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          <div className="mt-6 flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-1 text-sm">
              {t("sortLabel")}
              <select name="ordering" defaultValue={ordering} className={field}>
                {ORDERINGS.map((o) => (
                  <option key={o} value={o}>
                    {t(`sort.${o}`)}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="min-h-11 rounded-[var(--radius-control)] border border-secondary px-6 text-primary hover:bg-surface">
              {t("apply")}
            </button>
            {filtered ? (
              <Link href="/artworks" className="min-h-11 content-center px-2 text-sm text-muted underline">
                {t("clearFilters")}
              </Link>
            ) : null}
          </div>
        </details>
      </form>

      <nav aria-label={t("allCategories")} className="mt-8 flex flex-wrap gap-2">
        <Link href={hrefWith({ category: "" })} className={chip(filters.category === "")}>
          {t("allCategories")}
        </Link>
        {categories.map((c) => (
          <Link key={c.slug} href={hrefWith({ category: c.slug })} className={chip(filters.category === c.slug)}>
            {c.name}
          </Link>
        ))}
      </nav>
      {selected && selected.children.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {selected.children.map((child) => (
            <Link key={child.slug} href={hrefWith({ category: child.slug })} className={chip(false)}>
              {child.name}
            </Link>
          ))}
        </div>
      ) : null}

      <p className="mt-10 text-sm text-muted" aria-live="polite">
        {t("resultsCount", { count: artworks.count })}
      </p>
      <div className="mt-6">
        <ArtworkGrid artworks={artworks.results} emptyText={filtered ? t("noResults") : t("emptyArtworks")} />
      </div>
      <Pagination pathname="/artworks" page={page} totalPages={pageCount(artworks.count)} query={kept} />
    </Container>
  );
}
