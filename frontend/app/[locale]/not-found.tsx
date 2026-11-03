import { getTranslations } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <Container className="py-32 text-center">
      <h1 className="text-3xl font-semibold text-primary">{t("title")}</h1>
      <p className="mt-4 text-muted">{t("body")}</p>
      <Link href="/" className="mt-10 inline-block text-secondary underline underline-offset-4">
        {t("home")}
      </Link>
    </Container>
  );
}
