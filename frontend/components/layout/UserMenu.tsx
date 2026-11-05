"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { logout } from "@/features/auth/api";
import { useCartCount } from "@/features/cart/api";
import { Link, useRouter } from "@/i18n/navigation";
import { currentUserKey, useCurrentUser } from "@/lib/auth/useCurrentUser";

const iconLink =
  "relative inline-flex size-11 items-center justify-center rounded-full text-primary transition-colors duration-300 ease-calm hover:bg-surface";

function CartLink() {
  const t = useTranslations("nav");
  const count = useCartCount().data?.count ?? 0;
  return (
    <Link href="/cart" className={iconLink} aria-label={t("cartCount", { count })}>
      <Icon name="bag" className="size-6" />
      {count > 0 ? (
        <span
          aria-hidden
          className="absolute -end-0.5 top-0.5 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] leading-5 text-on-primary tabular-nums"
        >
          {count > 9 ? "9+" : count}
        </span>
      ) : null}
    </Link>
  );
}

const MAIN_LINKS = [
  { href: "/auctions", key: "auctions" },
  { href: "/artworks", key: "artworks" },
  { href: "/artists", key: "artists" },
  { href: "/archive", key: "archive" },
] as const;

/**
 * State-aware header actions (visitor / customer / staff) and the phone menu.
 * Only actions that make sense for the current account are rendered.
 */
export function UserMenu() {
  const t = useTranslations("nav");
  const { data: user, isPending } = useCurrentUser();
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();
  const panel = useRef<HTMLDivElement>(null);
  const isCustomer = Boolean(user && !user.is_staff);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    panel.current?.querySelector<HTMLElement>("a,button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  async function signOut() {
    await logout().catch(() => undefined);
    queryClient.clear();
    queryClient.setQueryData(currentUserKey, null);
    router.replace("/");
    router.refresh();
  }

  if (isPending) return <span className="inline-block h-11 w-24" aria-hidden />;

  const desktop = !user ? (
    <div className="hidden items-center gap-4 text-sm sm:flex">
      <Link href="/login" className="text-primary hover:text-secondary">
        {t("login")}
      </Link>
      <Link href="/register" className="rounded-[var(--radius-control)] border border-secondary px-3 py-1.5 text-primary hover:bg-surface">
        {t("register")}
      </Link>
    </div>
  ) : (
    <div className="hidden items-center gap-1 text-sm sm:flex">
      {user.is_staff ? (
        <Link href="/admin" className="px-3 text-primary hover:text-secondary">
          {t("admin")}
        </Link>
      ) : (
        <Link href="/favorites" className={iconLink} aria-label={t("favorites")}>
          <Icon name="heart" />
        </Link>
      )}
      <Link href="/account" className={iconLink} aria-label={t("account")}>
        <Icon name="user" />
      </Link>
    </div>
  );

  const menuItem = "block rounded-[var(--radius-control)] px-3 py-3 text-base text-text hover:bg-surface";
  return (
    <div className="flex items-center gap-1">
      {desktop}
      {isCustomer ? <CartLink /> : null}
      <button
        type="button"
        className={`${iconLink} sm:hidden`}
        aria-expanded={open}
        aria-controls="mobile-menu"
        aria-label={open ? t("closeMenu") : t("menu")}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name={open ? "close" : "menu"} className="size-6" />
      </button>
      {open ? (
        <div
          id="mobile-menu"
          ref={panel}
          // Close after choosing a destination (any link inside the panel).
          onClick={(e) => (e.target as HTMLElement).closest("a") && setOpen(false)}
          className="fixed inset-x-0 top-20 bottom-0 z-40 overflow-y-auto border-t border-border/60 bg-background px-4 py-4 sm:hidden"
        >
          <ul className="flex flex-col gap-1">
            {MAIN_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className={menuItem}>
                  {t(link.key)}
                </Link>
              </li>
            ))}
          </ul>
          <hr className="my-4 border-border/60" />
          {!user ? (
            <div className="flex flex-col gap-3">
              <Link href="/login" className="rounded-[var(--radius-control)] bg-primary px-4 py-3 text-center text-on-primary">
                {t("login")}
              </Link>
              <Link href="/register" className="rounded-[var(--radius-control)] border border-secondary px-4 py-3 text-center text-primary">
                {t("register")}
              </Link>
            </div>
          ) : (
            <ul className="flex flex-col gap-1">
              {user.is_staff ? (
                <li>
                  <Link href="/admin" className={menuItem}>
                    {t("admin")}
                  </Link>
                </li>
              ) : (
                <>
                  <li>
                    <Link href="/orders" className={menuItem}>
                      {t("orders")}
                    </Link>
                  </li>
                  <li>
                    <Link href="/bids" className={menuItem}>
                      {t("bids")}
                    </Link>
                  </li>
                  <li>
                    <Link href="/auction-requests" className={menuItem}>
                      {t("auctionRequests")}
                    </Link>
                  </li>
                  <li>
                    <Link href="/favorites" className={menuItem}>
                      {t("favorites")}
                    </Link>
                  </li>
                </>
              )}
              <li>
                <Link href="/account" className={menuItem}>
                  {t("account")}
                </Link>
              </li>
              <li>
                <button type="button" className={`${menuItem} w-full text-start text-muted`} onClick={signOut}>
                  {t("logout")}
                </button>
              </li>
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
