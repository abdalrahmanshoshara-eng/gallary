"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { applyServerErrors } from "@/lib/forms";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { currentUserKey } from "@/lib/auth/useCurrentUser";

import { register, type RegisterInput } from "./api";
import { GOVERNORATES, registerSchema, type RegisterValues } from "./schemas";

const FIELDS = [
  "phone",
  "first_name",
  "last_name",
  "email",
  "governorate",
  "city",
  "address_line",
  "password",
  "password_confirm",
];
const CLIENT_KEYS = new Set([
  "required",
  "emailInvalid",
  "passwordTooShort",
  "passwordLetterDigit",
  "passwordMismatch",
]);
const CODE_FIELDS: Record<string, "phone" | "email"> = {
  INVALID_PHONE: "phone",
  PHONE_IN_USE: "phone",
  EMAIL_IN_USE: "email",
};
const legendClass = "mb-4 text-lg font-medium text-primary";

export function RegisterForm({ next }: { next: string }) {
  const t = useTranslations("register");
  const ta = useTranslations("auth");
  const tg = useTranslations("governorates");
  const router = useRouter();
  const queryClient = useQueryClient();
  const uid = useId();
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      phone: "",
      first_name: "",
      last_name: "",
      email: "",
      governorate: "",
      city: "",
      address_line: "",
      password: "",
      password_confirm: "",
    },
  });
  const submit = useMutation({
    mutationFn: (values: RegisterValues) => register(registerSchema.parse(values) as RegisterInput),
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserKey, user);
      router.replace(next);
      router.refresh();
    },
    onError: (error) => {
      // Non-validation codes that belong to one field are shown under it, not at the top.
      const field = error instanceof ApiError ? CODE_FIELDS[error.code] : undefined;
      if (field) form.setError(field, { message: error.message }, { shouldFocus: true });
      else applyServerErrors(error, form.setError, FIELDS);
    },
  });
  const e = form.formState.errors;
  const msg = (m?: string) =>
    m === "phoneInvalid" ? ta("phoneInvalid") : m && CLIENT_KEYS.has(m) ? t(m as "required") : m;

  return (
    <form noValidate className="flex flex-col gap-10" onSubmit={form.handleSubmit((v) => submit.mutate(v))}>
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}

      <fieldset className="grid gap-6">
        <legend className={legendClass}>{t("personal")}</legend>
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label={t("firstName")} autoComplete="given-name" error={msg(e.first_name?.message)} {...form.register("first_name")} />
          <Field label={t("lastName")} autoComplete="family-name" error={msg(e.last_name?.message)} {...form.register("last_name")} />
        </div>
        <Field
          label={ta("phoneLabel")}
          hint={`${ta("phoneHint")} — ${t("phoneNotice")}`}
          type="tel"
          dir="ltr"
          autoComplete="tel"
          inputMode="tel"
          error={msg(e.phone?.message)}
          {...form.register("phone")}
        />
        <Field
          label={t("email")}
          hint={t("emailHint")}
          type="email"
          dir="ltr"
          autoComplete="email"
          error={msg(e.email?.message)}
          {...form.register("email")}
        />
      </fieldset>

      <fieldset className="grid gap-6">
        <legend className={legendClass}>{t("residence")}</legend>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${uid}-gov`} className="text-sm font-medium">
            {t("governorate")}
          </label>
          <select
            id={`${uid}-gov`}
            autoComplete="address-level1"
            aria-invalid={e.governorate ? true : undefined}
            aria-describedby={e.governorate ? `${uid}-gov-error` : undefined}
            className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
            {...form.register("governorate")}
          >
            <option value="">{t("chooseGovernorate")}</option>
            {GOVERNORATES.map((g) => (
              <option key={g} value={g}>
                {tg(g)}
              </option>
            ))}
          </select>
          {e.governorate ? (
            <p id={`${uid}-gov-error`} role="alert" className="text-sm text-primary">
              {msg(e.governorate.message)}
            </p>
          ) : null}
        </div>
        <Field label={t("city")} autoComplete="address-level2" error={msg(e.city?.message)} {...form.register("city")} />
        <Field
          label={t("addressLine")}
          hint={t("addressHint")}
          autoComplete="street-address"
          error={msg(e.address_line?.message)}
          {...form.register("address_line")}
        />
      </fieldset>

      <fieldset className="grid gap-6">
        <legend className={legendClass}>{t("security")}</legend>
        <Field
          label={t("password")}
          hint={t("passwordRules")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          error={msg(e.password?.message)}
          {...form.register("password")}
        />
        <Field
          label={t("passwordConfirm")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          error={msg(e.password_confirm?.message)}
          {...form.register("password_confirm")}
        />
      </fieldset>

      <Button type="submit" loading={submit.isPending}>
        {submit.isPending ? t("submitting") : t("submit")}
      </Button>
      <p className="text-sm">
        {t("haveAccount")}{" "}
        <Link href={{ pathname: "/login", query: next !== "/" ? { next } : {} }} className="text-secondary underline">
          {t("login")}
        </Link>
      </p>
    </form>
  );
}
