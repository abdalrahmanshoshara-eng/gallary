import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { Container } from "@/components/ui/Container";
import { Pagination } from "@/components/ui/Pagination";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import { pageCount, parsePage, type ArtworkCardData, type CategoryNode, type Page } from "@/lib/catalog/types";

const ORDERINGS = ["newest", "oldest", "title", "year"] as const;
type Ordering = (typeof ORDERINGS)[number];

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("catalog");
  return { title: t("artworksTitle"), description: t("artworksIntro") };
}

export default async function ArtworksPage({ params, searchParams }: PageProps<"/[locale]/artworks">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const query = await searchParams;
  const t = await getTranslations("catalog");

  const category = typeof query.category === "string" ? query.category : "";
  const ordering: Ordering = ORDERINGS.includes(query.ordering as Ordering) ? (query.ordering as Ordering) : "newest";
  const page = parsePage(query.page);

  const [categories, artworks] = await Promise.all([
    publicApiGet<CategoryNode[]>("/catalog/categories", undefined, 300),
    publicApiGet<Page<ArtworkCardData>>("/artworks", {
      category,
      ordering: ordering === "newest" ? undefined : ordering,
      page: page > 1 ? page : undefined,
    }),
  ]);

  const chip = (active: boolean) =>
    [
      "rounded-full border px-4 py-1.5 text-sm transition-colors duration-300 ease-calm",
      active ? "border-primary bg-primary text-on-primary" : "border-border text-text hover:border-secondary",
    ].join(" ");
  const categoryHref = (slug: string) => {
    const qs = new URLSearchParams(Object.entries({ category: slug, ordering: ordering === "newest" ? "" : ordering }).filter(([, v]) => v));
    return qs.toString() ? `/artworks?${qs}` : "/artworks";
  };

  return (
    <Container className="py-16">
      <header className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-primary md:text-4xl">{t("artworksTitle")}</h1>
        <p className="mt-4 text-muted">{t("artworksIntro")}</p>
      </header>

      <div className="mt-12 flex flex-col gap-6 border-y border-border/50 py-6 lg:flex-row lg:items-center lg:justify-between">
        <nav aria-label={t("allCategories")} className="flex flex-wrap gap-2">
          <Link href={categoryHref("")} className={chip(category === "")}>
            {t("allCategories")}
          </Link>
          {categories.map((c) => (
            <Link key={c.slug} href={categoryHref(c.slug)} className={chip(category === c.slug)}>
              {c.name}
            </Link>
          ))}
        </nav>
        <form method="get" className="flex items-center gap-3 text-sm">
          {category ? <input type="hidden" name="category" value={category} /> : null}
          <label htmlFor="ordering" className="text-muted">
            {t("sortLabel")}
          </label>
          <select
            id="ordering"
            name="ordering"
            defaultValue={ordering}
            className="min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3"
          >
            {ORDERINGS.map((o) => (
              <option key={o} value={o}>
                {t(`sort.${o}`)}
              </option>
            ))}
          </select>
          <button type="submit" className="min-h-10 px-3 text-primary hover:text-secondary">
            {t("apply")}
          </button>
        </form>
      </div>

      {/* Sub-categories of the selected category, when it has any. */}
      {(() => {
        const selected = categories.find((c) => c.slug === category);
        if (!selected || selected.children.length === 0) return null;
        return (
          <div className="mt-6 flex flex-wrap gap-2">
            {selected.children.map((child) => (
              <Link key={child.slug} href={categoryHref(child.slug)} className={chip(false)}>
                {child.name}
              </Link>
            ))}
          </div>
        );
      })()}

      <div className="mt-12">
        <ArtworkGrid artworks={artworks.results} emptyText={t("emptyArtworks")} />
      </div>
      <Pagination
        pathname="/artworks"
        page={page}
        totalPages={pageCount(artworks.count)}
        query={{ category: category || undefined, ordering: ordering === "newest" ? undefined : ordering }}
      />
    </Container>
  );
}
