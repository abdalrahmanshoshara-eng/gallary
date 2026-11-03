import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { ProfileForm } from "@/features/account/ProfileForm";
import { SessionsPanel } from "@/features/account/SessionsPanel";
import { LogoutButton } from "@/features/auth/LogoutButton";
import { requireUser } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("account");
  return { title: t("title"), robots: { index: false } };
}

export default async function AccountPage({ params }: PageProps<"/[locale]/account">) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await requireUser(locale, "/account");
  const t = await getTranslations("account");

  return (
    <Container className="max-w-3xl py-16">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
        <LogoutButton />
      </div>
      <section aria-labelledby="profile" className="mt-14">
        <h2 id="profile" className="mb-8 text-xl font-medium text-primary">
          {t("profile")}
        </h2>
        <ProfileForm user={user} />
      </section>
      <section aria-labelledby="sessions" className="mt-16">
        <h2 id="sessions" className="text-xl font-medium text-primary">
          {t("sessions")}
        </h2>
        <p className="mt-2 mb-6 text-sm text-muted">{t("sessionsIntro")}</p>
        <SessionsPanel />
      </section>
    </Container>
  );
}
