"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ApiError } from "@/lib/api/errors";

import { getSettings, settingsKey, updateSettings, type SiteSettings } from "./api";

function Form({ initial, editable }: { initial: SiteSettings; editable: boolean }) {
  const t = useTranslations("admin.settings");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [values, setValues] = useState({
    default_commission_rate: initial.default_commission_rate ?? "",
    default_deposit_type: initial.default_deposit_type ?? "percentage",
    default_deposit_value: initial.default_deposit_value ?? "",
    whatsapp_number: initial.whatsapp_number ?? "",
    max_pending_orders_per_user: String(initial.max_pending_orders_per_user ?? 3),
  });
  const set = (key: keyof typeof values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [key]: e.target.value }));
  const save = useMutation({
    mutationFn: () => updateSettings({ ...values, max_pending_orders_per_user: Number(values.max_pending_orders_per_user) }),
    onSuccess: (saved) => queryClient.setQueryData(settingsKey, saved),
  });
  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors : {};
  const err = (k: string) => fieldErrors[k]?.join(" ");

  return (
    <form
      noValidate
      className="flex max-w-xl flex-col gap-6"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      {!editable ? <Alert tone="info">{t("readOnly")}</Alert> : null}
      {save.isSuccess ? <Alert tone="success">{t("saved")}</Alert> : null}
      {save.error && !Object.keys(fieldErrors).length ? <Alert tone="error">{(save.error as Error).message}</Alert> : null}
      <fieldset disabled={!editable} className="flex flex-col gap-6">
        <Field label={t("commission")} inputMode="decimal" dir="ltr" value={values.default_commission_rate} error={err("default_commission_rate")} onChange={set("default_commission_rate")} />
        <div className="grid gap-6 sm:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm font-medium">
            {t("depositType")}
            <select
              className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
              value={values.default_deposit_type}
              onChange={set("default_deposit_type")}
            >
              <option value="percentage">{t("depositPercentage")}</option>
              <option value="fixed">{t("depositFixed")}</option>
            </select>
          </label>
          <Field label={t("depositValue")} inputMode="decimal" dir="ltr" value={values.default_deposit_value} error={err("default_deposit_value")} onChange={set("default_deposit_value")} />
        </div>
        <Field label={t("whatsapp")} type="tel" dir="ltr" value={values.whatsapp_number} error={err("whatsapp_number")} onChange={set("whatsapp_number")} />
        <Field label={t("maxPending")} inputMode="numeric" dir="ltr" value={values.max_pending_orders_per_user} error={err("max_pending_orders_per_user")} onChange={set("max_pending_orders_per_user")} />
        {editable ? (
          <div>
            <Button type="submit" loading={save.isPending}>
              {tc("save")}
            </Button>
          </div>
        ) : null}
      </fieldset>
    </form>
  );
}

export function SettingsForm({ editable }: { editable: boolean }) {
  const tc = useTranslations("common");
  const settings = useQuery({ queryKey: settingsKey, queryFn: getSettings });
  if (settings.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (settings.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  return <Form initial={settings.data} editable={editable} />;
}
