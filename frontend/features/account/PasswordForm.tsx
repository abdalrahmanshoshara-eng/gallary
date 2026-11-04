"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { changePassword } from "@/features/auth/api";
import { newPasswordField } from "@/features/auth/schemas";
import { ApiError } from "@/lib/api/errors";

const schema = z
  .object({
    current_password: z.string().min(1, "required"),
    new_password: newPasswordField,
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { message: "passwordMismatch", path: ["confirm"] });
type Values = z.infer<typeof schema>;
const KEYS = new Set(["required", "passwordTooShort", "passwordLetterDigit", "passwordMismatch"]);

export function PasswordForm() {
  const t = useTranslations("account");
  const tr = useTranslations("register");
  const queryClient = useQueryClient();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const save = useMutation({
    mutationFn: (v: Values) => changePassword(v.current_password, v.new_password),
    onSuccess: () => {
      form.reset();
      void queryClient.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      if (error.code === "WRONG_PASSWORD") form.setError("current_password", { message: error.message });
      else if (error.fieldErrors.password) form.setError("new_password", { message: error.fieldErrors.password.join(" ") });
      else form.setError("root", { message: error.message });
    },
  });
  const e = form.formState.errors;
  const msg = (m?: string) => (m && KEYS.has(m) ? tr(m as "required") : m);

  return (
    <form noValidate className="flex flex-col gap-6" onSubmit={form.handleSubmit((v) => save.mutate(v))}>
      {save.isSuccess ? <Alert tone="success">{t("passwordChanged")}</Alert> : null}
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}
      <Field
        label={t("currentPassword")}
        type="password"
        dir="ltr"
        autoComplete="current-password"
        error={msg(e.current_password?.message)}
        {...form.register("current_password")}
      />
      <div className="grid gap-6 sm:grid-cols-2">
        <Field
          label={t("newPassword")}
          hint={tr("passwordRules")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          error={msg(e.new_password?.message)}
          {...form.register("new_password")}
        />
        <Field
          label={t("newPasswordConfirm")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          error={msg(e.confirm?.message)}
          {...form.register("confirm")}
        />
      </div>
      <div>
        <Button type="submit" loading={save.isPending}>
          {t("changePassword")}
        </Button>
      </div>
    </form>
  );
}
