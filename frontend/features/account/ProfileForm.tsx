"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { GOVERNORATES } from "@/features/auth/schemas";
import { ApiError } from "@/lib/api/errors";
import type { Schema } from "@/lib/api/types";
import type { CurrentUser } from "@/lib/auth/types";
import { currentUserKey } from "@/lib/auth/useCurrentUser";
import { applyServerErrors } from "@/lib/forms";

import { updateProfile } from "./api";

const schema = z.object({
  first_name: z.string().trim().max(60),
  last_name: z.string().trim().max(60),
  email: z.union([z.literal(""), z.email("emailInvalid")]),
  governorate: z.string(),
  city: z.string().trim().max(100),
  address_line: z.string().trim().max(255),
});
type Values = z.infer<typeof schema>;
const FIELDS = Object.keys(schema.shape);

const fromUser = (u: CurrentUser): Values => ({
  first_name: u.first_name ?? "",
  last_name: u.last_name ?? "",
  email: u.email ?? "",
  governorate: u.governorate ?? "",
  city: u.city ?? "",
  address_line: u.address_line ?? "",
});

export function ProfileForm({ user }: { user: CurrentUser }) {
  const t = useTranslations("account");
  const tr = useTranslations("register");
  const tg = useTranslations("governorates");
  const tc = useTranslations("common");
  const uid = useId();
  const queryClient = useQueryClient();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: fromUser(user) });
  const save = useMutation({
    mutationFn: (v: Values) => updateProfile(v as Schema<"PatchedProfileUpdateRequest">),
    onSuccess: (updated) => {
      queryClient.setQueryData(currentUserKey, updated);
      form.reset(fromUser(updated));
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "EMAIL_IN_USE") {
        form.setError("email", { message: error.message });
        return;
      }
      applyServerErrors(error, form.setError, FIELDS);
    },
  });
  const emailError = form.formState.errors.email?.message;

  return (
    <form noValidate className="flex flex-col gap-6" onSubmit={form.handleSubmit((v) => save.mutate(v))}>
      {save.isSuccess && !form.formState.isDirty ? <Alert tone="success">{t("saved")}</Alert> : null}
      {form.formState.errors.root ? <Alert tone="error">{form.formState.errors.root.message}</Alert> : null}
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">{t("phone")}</span>
        <bdi dir="ltr" className="text-start text-muted">
          {user.phone}
        </bdi>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
        <Field label={t("firstName")} autoComplete="given-name" {...form.register("first_name")} />
        <Field label={t("lastName")} autoComplete="family-name" {...form.register("last_name")} />
      </div>
      <Field
        label={t("email")}
        type="email"
        dir="ltr"
        autoComplete="email"
        error={emailError === "emailInvalid" ? t("emailInvalid") : emailError}
        {...form.register("email")}
      />
      <fieldset className="grid gap-6">
        <legend className="mb-2 text-sm font-medium">{t("residence")}</legend>
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label htmlFor={`${uid}-gov`} className="text-sm font-medium">
              {tr("governorate")}
            </label>
            <select
              id={`${uid}-gov`}
              className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
              {...form.register("governorate")}
            >
              <option value="">{tr("chooseGovernorate")}</option>
              {GOVERNORATES.map((g) => (
                <option key={g} value={g}>
                  {tg(g)}
                </option>
              ))}
            </select>
          </div>
          <Field label={tr("city")} autoComplete="address-level2" {...form.register("city")} />
        </div>
        <Field label={tr("addressLine")} autoComplete="street-address" {...form.register("address_line")} />
      </fieldset>
      <div>
        <Button type="submit" loading={save.isPending} disabled={!form.formState.isDirty}>
          {save.isPending ? tc("saving") : tc("save")}
        </Button>
      </div>
    </form>
  );
}
