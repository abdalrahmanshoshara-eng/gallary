import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { Link } from "@/i18n/navigation";
import { publicApiGet } from "@/lib/api/public";
import type { Schema } from "@/lib/api/types";
import { Markdown } from "@/lib/markdown";

// Rendered per request (data cached 5 min): builds never depend on the API being up.
export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("content");
  return { title: t("faqTitle"), description: t("faqIntro") };
}

export default async function FaqPage({ params }: PageProps<"/[locale]/faq">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("content");
  const items = await publicApiGet<Schema<"PublicFaq">[]>("/faq", undefined, 300);
  return (
    <Container className="py-16">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-semibold text-primary md:text-4xl">{t("faqTitle")}</h1>
        <p className="mt-3 text-muted">{t("faqIntro")}</p>
        {items.length === 0 ? (
          <p className="mt-12 text-muted">{t("faqEmpty")}</p>
        ) : (
          <div className="mt-10 divide-y divide-border/60 border-y border-border/60">
            {items.map((item) => (
              <details key={item.id} className="group py-1">
                <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 py-3 text-lg font-medium text-primary marker:hidden [&::-webkit-details-marker]:hidden">
                  {item.question}
                  <Icon name="plus" className="size-5 shrink-0 text-secondary transition-transform duration-300 ease-calm group-open:rotate-45" />
                </summary>
                <Markdown source={item.answer} className="pb-5 text-base" />
              </details>
            ))}
          </div>
        )}
        <p className="mt-10 text-sm text-muted">
          {t("faqMore")}{" "}
          <Link href="/deposit-policy" className="text-primary underline underline-offset-4">
            {t("faqPolicy")}
          </Link>
        </p>
      </div>
    </Container>
  );
}
