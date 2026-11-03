import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { LoginForm } from "@/features/auth/LoginForm";
import { safeNextPath } from "@/lib/navigation/safe-next";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth");
  return { title: t("title"), robots: { index: false } };
}

export default async function LoginPage({ params, searchParams }: PageProps<"/[locale]/login">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("auth");
  const next = safeNextPath(((await searchParams)["next"] as string | undefined) ?? null);

  return (
    <Container className="max-w-md py-20">
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-3 mb-10 text-muted">{t("intro")}</p>
      <LoginForm next={next} />
      <p className="mt-10 text-xs text-muted">{t("terms")}</p>
    </Container>
  );
}
