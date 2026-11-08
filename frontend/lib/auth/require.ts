import "server-only";

import { notFound } from "next/navigation";

import { redirect } from "@/i18n/navigation";

import { getCurrentUser } from "./server";
import type { CurrentUser } from "./types";

/** Server-side guard for signed-in pages: redirects to login, preserving the target. */
export async function requireUser(locale: string, path: string): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (!user) return redirect({ href: { pathname: "/login", query: { next: path } }, locale });
  return user;
}

/** Staff-only pages: anonymous → login; customers get a plain 404 (no hint the page exists). */
export async function requireStaff(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireUser(locale, path);
  if (!user.is_staff) notFound();
  return user;
}

export async function requireSuperAdmin(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireStaff(locale, path);
  if (!user.is_super_admin) notFound();
  return user;
}

/** Catalogue management: content staff and Super Admin (PRD §8). */
export async function requireCatalogEditor(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireStaff(locale, path);
  if (!user.roles.some((r) => r === "content_staff" || r === "super_admin")) notFound();
  return user;
}

/** Shopping pages (cart, checkout, orders, favourites): customer accounts only (PRD §8). */
export async function requireCustomer(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireUser(locale, path);
  if (user.is_staff) notFound();
  return user;
}

/** Orders, payments and delivery: operations staff and Super Admin; auction managers for
 * their auctions' orders only (the API narrows the list). */
export async function requireOrderDesk(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireStaff(locale, path);
  if (!user.roles.some((r) => r === "operations_staff" || r === "super_admin" || r === "auction_manager")) notFound();
  return user;
}

/** Auctions and auction requests: auction managers and Super Admin (PRD §8). */
export async function requireAuctionStaff(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireStaff(locale, path);
  if (!user.roles.some((r) => r === "auction_manager" || r === "super_admin")) notFound();
  return user;
}

/** Settlements: operations staff and Super Admin (decision 2026-11-08). */
export async function requireOrdersStaff(locale: string, path: string): Promise<CurrentUser> {
  const user = await requireStaff(locale, path);
  if (!user.roles.some((r) => r === "operations_staff" || r === "super_admin")) notFound();
  return user;
}
