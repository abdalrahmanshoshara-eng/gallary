import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Container } from "@/components/ui/Container";
import { Link } from "@/i18n/navigation";
import { getCurrentUser } from "@/lib/auth/server";
import { isCatalogEditor, isOrdersStaff } from "@/lib/auth/types";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function AdminLayout({ children, params }: LayoutProps<"/[locale]/admin">) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Each admin page guards itself with its own path (layouts cannot know the current URL,
  // so a redirect here would lose ?next=). Django re-authorises every admin API call.
  const user = await getCurrentUser();
  if (!user?.is_staff) return children;
  const t = await getTranslations("admin");

  const links = [
    { href: "/admin" as const, label: t("home") },
    ...(isOrdersStaff(user) ? [{ href: "/admin/orders" as const, label: t("orders.title") }] : []),
    ...(isCatalogEditor(user)
      ? [
          { href: "/admin/artworks" as const, label: t("artworks.title") },
          { href: "/admin/artists" as const, label: t("artists.title") },
          { href: "/admin/catalog" as const, label: t("terms.title") },
          { href: "/admin/settings" as const, label: t("settings.title") },
        ]
      : []),
    ...(user.is_super_admin
      ? [
          { href: "/admin/staff" as const, label: t("staff.title") },
          { href: "/admin/users" as const, label: t("users.title") },
        ]
      : []),
  ];

  return (
    <Container className="py-12">
      <div className="flex flex-col gap-10 md:flex-row">
        <nav aria-label={t("sectionsLabel")} className="md:w-56 md:shrink-0">
          <p className="mb-4 text-sm text-muted">{t("title")}</p>
          <ul className="flex flex-wrap gap-4 md:flex-col md:gap-2">
            {links.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="text-primary hover:text-secondary">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </Container>
  );
}
