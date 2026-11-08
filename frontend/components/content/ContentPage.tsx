import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { publicApiGetOrNull } from "@/lib/api/public";
import type { Schema } from "@/lib/api/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { Markdown } from "@/lib/markdown";

type PublicPage = Schema<"PublicPage">;
export type ContentSlug = "about" | "terms" | "privacy" | "deposit-policy";

export const loadPage = (slug: ContentSlug) => publicApiGetOrNull<PublicPage>(`/pages/${slug}`, 300);

export async function contentMetadata(slug: ContentSlug): Promise<Metadata> {
  const page = await loadPage(slug);
  if (!page) return {};
  const firstLine = page.body.split("\n").find((l) => l.trim() && !l.startsWith("#") && !l.startsWith(">")) ?? "";
  return { title: page.title, description: firstLine.replace(/^[-*>\d.)\s]+/, "").slice(0, 160) };
}

/** A published CMS page (F-CMS-01); unpublished pages are 404. */
export async function ContentPage({ slug }: { slug: ContentSlug }) {
  const page = await loadPage(slug);
  if (!page) notFound();
  const t = await getTranslations("content");
  return (
    <Container className="py-16">
      <article className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-semibold text-primary md:text-4xl">{page.title}</h1>
        <Markdown source={page.body} className="mt-8 text-base" />
        <p className="mt-12 border-t border-border/50 pt-4 text-xs text-muted">{t("updated", { date: formatDateTime(page.published_at) })}</p>
      </article>
    </Container>
  );
}
