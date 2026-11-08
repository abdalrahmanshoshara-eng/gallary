"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId } from "react";

import { Link } from "@/i18n/navigation";

import { getPreferences, preferencesKey, updatePreferences } from "./api";

/**
 * "Send me an e-mail copy" switch. Hidden when the platform does not send e-mail; disabled
 * with a pointer to the account page when the customer has no address.
 */
export function EmailPreference() {
  const t = useTranslations("notifications.email");
  const id = useId();
  const queryClient = useQueryClient();
  const prefs = useQuery({ queryKey: preferencesKey, queryFn: getPreferences });
  const save = useMutation({
    mutationFn: updatePreferences,
    onSuccess: (data) => queryClient.setQueryData(preferencesKey, data),
  });

  const p = prefs.data;
  if (!p || !p.email_available) return null;
  const checked =
    p.has_email && (save.isPending ? Boolean(save.variables) : p.email_enabled);

  return (
    <section
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-2 border-t border-border/60 pt-6"
    >
      <h2 id={`${id}-title`} className="text-base font-medium text-primary">
        {t("title")}
      </h2>
      <div className="flex items-start justify-between gap-4">
        <p id={`${id}-desc`} className="text-sm leading-6 text-muted">
          {p.has_email ? t("description") : t("noAddress")}{" "}
          {p.has_email ? null : (
            <Link
              href="/account"
              className="text-primary underline underline-offset-4"
            >
              {t("addAddress")}
            </Link>
          )}
        </p>
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-desc`}
          disabled={!p.has_email || save.isPending}
          onClick={() => save.mutate(!p.email_enabled)}
          className={`relative inline-block h-7 w-12 shrink-0 rounded-full transition-colors duration-300 ease-calm disabled:opacity-50 ${
            checked ? "bg-primary" : "bg-border"
          }`}
        >
          <span
            aria-hidden
            className={`absolute top-1 size-5 rounded-full bg-white shadow transition-all duration-300 ease-calm ${checked ? "start-6" : "start-1"}`}
          />
        </button>
      </div>
      {save.isError ? (
        <p role="alert" className="text-sm text-primary">
          {t("error")}
        </p>
      ) : null}
    </section>
  );
}
