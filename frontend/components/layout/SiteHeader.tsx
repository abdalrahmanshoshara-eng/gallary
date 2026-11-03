import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";

export async function SiteHeader() {
  const t = await getTranslations();
  return (
    <header className="border-b border-border/60 bg-background/95">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:bg-white focus:px-4 focus:py-2"
      >
        {t("nav.skipToContent")}
      </a>
      <Container className="flex h-20 items-center justify-between">
        <Link href="/" className="font-heading text-xl font-semibold text-primary">
          {t("brand.name")}
        </Link>
        {/* Navigation links are added with their pages (Phase 3+); no dead links. */}
        <nav aria-label={t("nav.label")} />
      </Container>
    </header>
  );
}
