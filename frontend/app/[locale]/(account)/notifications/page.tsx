import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccountTabs } from "@/components/layout/AccountTabs";
import { Container } from "@/components/ui/Container";
import { NotificationsCenter } from "@/features/notifications/NotificationsCenter";
import { requireCustomer } from "@/lib/auth/require";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications");
  return { title: t("title"), robots: { index: false } };
}

export default async function NotificationsPage({
  params,
}: PageProps<"/[locale]/notifications">) {
  const { locale } = await params;
  setRequestLocale(locale);
  await requireCustomer(locale, "/notifications");
  const t = await getTranslations("notifications");
  return (
    <Container className="py-12">
      <AccountTabs />
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-2 text-3xl font-semibold text-primary">
          {t("title")}
        </h1>
        <p className="mb-8 text-sm text-muted">{t("intro")}</p>
        <NotificationsCenter />
      </div>
    </Container>
  );
}
