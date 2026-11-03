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
