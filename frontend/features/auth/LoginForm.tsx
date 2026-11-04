"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { currentUserKey } from "@/lib/auth/useCurrentUser";

import { login } from "./api";
import { loginSchema, type LoginValues } from "./schemas";

const CLIENT_KEYS = new Set(["phoneInvalid", "passwordRequired"]);

export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { phone: "", password: "" } });

  const submit = useMutation({
    mutationFn: (values: LoginValues) => {
      const parsed = loginSchema.parse(values);
      return login(parsed.phone, parsed.password);
    },
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserKey, user);
      router.replace(next);
      router.refresh();
    },
    onError: (error) => {
      form.resetField("password");
      form.setError("root", { message: error instanceof ApiError ? error.message : String(error) });
    },
  });
  const e = form.formState.errors;
  const msg = (m?: string) => (m && CLIENT_KEYS.has(m) ? t(m as "phoneInvalid") : m);

  return (
    <form noValidate className="flex flex-col gap-6" onSubmit={form.handleSubmit((v) => submit.mutate(v))}>
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}
      <Field
        label={t("phoneLabel")}
        hint={t("phoneHint")}
        type="tel"
        dir="ltr"
        autoComplete="tel"
        inputMode="tel"
        error={msg(e.phone?.message)}
        {...form.register("phone")}
      />
      <Field
        label={t("passwordLabel")}
        type="password"
        dir="ltr"
        autoComplete="current-password"
        error={msg(e.password?.message)}
        {...form.register("password")}
      />
      <Button type="submit" loading={submit.isPending}>
        {submit.isPending ? t("submitting") : t("submit")}
      </Button>
      <p className="text-sm text-muted">{t("forgotPassword")}</p>
      <p className="text-sm">
        {t("noAccount")}{" "}
        <Link href={{ pathname: "/register", query: next !== "/" ? { next } : {} }} className="text-secondary underline">
          {t("createAccount")}
        </Link>
      </p>
    </form>
  );
}
