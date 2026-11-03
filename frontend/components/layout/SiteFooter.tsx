import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";

export async function SiteFooter() {
  const t = await getTranslations("footer");
  return (
    <footer className="mt-24 border-t border-border/60 bg-surface/40 py-10 text-sm text-muted">
      <Container className="flex flex-col gap-2 md:flex-row md:justify-between">
        <p>{t("rights", { year: new Date().getFullYear() })}</p>
        <p>{t("currency")}</p>
      </Container>
    </footer>
  );
}
