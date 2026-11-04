"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";

export function UserMenu() {
  const t = useTranslations("nav");
  const { data: user, isPending } = useCurrentUser();

  if (isPending) return <span className="inline-block h-5 w-24" aria-hidden />;
  if (!user) {
    return (
      <div className="flex items-center gap-4 text-sm">
        <Link href="/login" className="text-primary hover:text-secondary">
          {t("login")}
        </Link>
        <Link
          href="/register"
          className="rounded-[var(--radius-control)] border border-secondary px-3 py-1.5 text-primary hover:bg-surface"
        >
          {t("register")}
        </Link>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-6 text-sm">
      {user.is_staff ? (
        <Link href="/admin" className="text-primary hover:text-secondary">
          {t("admin")}
        </Link>
      ) : null}
      <Link href="/account" className="text-primary hover:text-secondary">
        {t("account")}
      </Link>
    </div>
  );
}
