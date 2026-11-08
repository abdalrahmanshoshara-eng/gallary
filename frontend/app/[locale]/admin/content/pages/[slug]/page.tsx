import { notFound } from "next/navigation";
import { setRequestLocale } from "next-intl/server";

import { PageEditor } from "@/features/admin-content/PageEditor";
import { requireCatalogEditor } from "@/lib/auth/require";

const SLUGS = ["about", "terms", "privacy", "deposit-policy"];

export default async function EditContentPage({ params }: PageProps<"/[locale]/admin/content/pages/[slug]">) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  if (!SLUGS.includes(slug)) notFound();
  await requireCatalogEditor(locale, `/admin/content/pages/${slug}`);
  return <PageEditor slug={slug} />;
}
