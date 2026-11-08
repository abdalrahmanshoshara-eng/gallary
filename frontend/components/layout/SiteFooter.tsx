import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import type { Schema } from "@/lib/api/types";

const ORDER = ["about", "terms", "privacy", "deposit-policy"];

export async function SiteFooter() {
  const t = await getTranslations("footer");
  // Only published pages are linked; a CMS outage must never break the footer.
  const pages = await publicApiGet<Schema<"PageLink">[]>(
    "/pages",
    undefined,
    300,
  ).catch(() => []);
  const links = [...pages].sort(
    (a, b) => ORDER.indexOf(a.slug) - ORDER.indexOf(b.slug),
  );
  return (
    <footer className="mt-24 border-t border-border/60 bg-surface/40 py-10 text-sm text-muted">
      <Container className="flex flex-col gap-6">
        <nav aria-label={t("links")}>
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {links.map((page) => (
              <li key={page.slug}>
                <Link
                  href={`/${page.slug}` as "/about"}
                  className="hover:text-primary"
                >
                  {page.title}
                </Link>
              </li>
            ))}
            <li>
              <Link href="/faq" className="hover:text-primary">
                {t("faq")}
              </Link>
            </li>
          </ul>
        </nav>
        <div className="flex flex-col gap-2 md:flex-row md:justify-between">
          <p>{t("rights", { year: new Date().getFullYear() })}</p>
          <p>{t("currency")}</p>
        </div>
      </Container>
    </footer>
  );
}
