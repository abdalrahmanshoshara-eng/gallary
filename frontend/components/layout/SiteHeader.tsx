import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { UserMenu } from "@/components/layout/UserMenu";
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
        <nav aria-label={t("nav.label")} className="flex items-center gap-6 text-sm md:gap-8">
          <ul className="hidden items-center gap-6 sm:flex">
            <li>
              <Link href="/auctions" className="text-text hover:text-secondary">
                {t("nav.auctions")}
              </Link>
            </li>
            <li>
              <Link href="/artworks" className="text-text hover:text-secondary">
                {t("nav.artworks")}
              </Link>
            </li>
            <li>
              <Link href="/artists" className="text-text hover:text-secondary">
                {t("nav.artists")}
              </Link>
            </li>
            <li>
              <Link href="/archive" className="text-text hover:text-secondary">
                {t("nav.archive")}
              </Link>
            </li>
          </ul>
          <UserMenu />
        </nav>
      </Container>
    </header>
  );
}
