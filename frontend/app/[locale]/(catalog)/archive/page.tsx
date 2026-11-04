import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ArtworkGrid } from "@/components/art/ArtworkCard";
import { Container } from "@/components/ui/Container";
import { Pagination } from "@/components/ui/Pagination";
import { publicApiGet } from "@/lib/api/public";
import { pageCount, parsePage, type ArtworkCardData, type Page } from "@/lib/catalog/types";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("catalog");
  return { title: t("archiveTitle"), description: t("archiveIntro") };
}

export default async function ArchivePage({ params, searchParams }: PageProps<"/[locale]/archive">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const page = parsePage((await searchParams).page);
  const t = await getTranslations("catalog");
  const artworks = await publicApiGet<Page<ArtworkCardData>>("/archive", { page: page > 1 ? page : undefined });

  return (
    <Container className="py-16">
      <h1 className="text-3xl font-semibold text-primary md:text-4xl">{t("archiveTitle")}</h1>
      <p className="mt-4 max-w-2xl text-muted">{t("archiveIntro")}</p>
      <div className="mt-12">
        <ArtworkGrid artworks={artworks.results} emptyText={t("emptyArchive")} />
      </div>
      <Pagination pathname="/archive" page={page} totalPages={pageCount(artworks.count)} />
    </Container>
  );
}
