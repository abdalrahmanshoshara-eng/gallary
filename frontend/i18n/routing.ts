import { defineRouting } from "next-intl/routing";

/**
 * Arabic only in the MVP. `as-needed` keeps Arabic URLs unprefixed, so adding English
 * later (/en/...) does not change any existing Arabic URL (ADR-14).
 */
export const routing = defineRouting({
  locales: ["ar"],
  defaultLocale: "ar",
  localePrefix: "as-needed",
});

export type Locale = (typeof routing.locales)[number];

const RTL_LOCALES: ReadonlySet<string> = new Set(["ar"]);

export function directionOf(locale: string): "rtl" | "ltr" {
  return RTL_LOCALES.has(locale) ? "rtl" : "ltr";
}
