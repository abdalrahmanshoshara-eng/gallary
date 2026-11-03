import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";

const PILLARS = ["curated", "auctions", "archive"] as const;

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");

  return (
    <>
      <section className="py-24 md:py-36">
        <Container className="max-w-3xl text-center">
          <p className="mb-6 text-sm tracking-wide text-secondary">{t("eyebrow")}</p>
          <h1 className="text-3xl font-semibold text-primary md:text-5xl">{t("title")}</h1>
          <p className="mx-auto mt-8 max-w-2xl text-lg text-muted">{t("intro")}</p>
        </Container>
      </section>
      <section aria-labelledby="pillars" className="border-t border-border/50 py-20">
        <h2 id="pillars" className="sr-only">
          {t("eyebrow")}
        </h2>
        <Container className="grid gap-12 md:grid-cols-3">
          {PILLARS.map((key) => (
            <article key={key} className="text-start">
              <h3 className="text-xl font-medium text-primary">{t(`pillars.${key}.title`)}</h3>
              <p className="mt-3 text-muted">{t(`pillars.${key}.body`)}</p>
            </article>
          ))}
        </Container>
      </section>
    </>
  );
}
