import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { ContentPage, contentMetadata } from "@/components/content/ContentPage";

// Rendered per request (data cached 5 min): builds never depend on the API being up.
export const dynamic = "force-dynamic";

export function generateMetadata(): Promise<Metadata> {
  return contentMetadata("deposit-policy");
}

export default async function Page({ params }: PageProps<"/[locale]/deposit-policy">) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ContentPage slug="deposit-policy" />;
}
