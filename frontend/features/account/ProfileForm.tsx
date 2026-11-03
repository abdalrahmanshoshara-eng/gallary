"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ApiError } from "@/lib/api/errors";
import type { CurrentUser } from "@/lib/auth/types";
import { currentUserKey } from "@/lib/auth/useCurrentUser";

import { updateProfile } from "./api";

const schema = z.object({
  display_name: z.string().trim().max(120),
  email: z.union([z.literal(""), z.email("emailInvalid")]),
});
type Values = z.infer<typeof schema>;

export function ProfileForm({ user }: { user: CurrentUser }) {
  const t = useTranslations("account");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: user.display_name, email: user.email ?? "" },
  });
  const save = useMutation({
    mutationFn: updateProfile,
    onSuccess: (updated) => {
      queryClient.setQueryData(currentUserKey, updated);
      form.reset({ display_name: updated.display_name, email: updated.email ?? "" });
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      const field = error.code === "EMAIL_IN_USE" ? "email" : "root";
      form.setError(field, { message: error.message });
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
      <Field label={t("displayName")} autoComplete="name" {...form.register("display_name")} />
      <Field
        label={t("email")}
        type="email"
        dir="ltr"
        autoComplete="email"
        error={emailError === "emailInvalid" ? t("emailInvalid") : emailError}
        {...form.register("email")}
      />
      <div>
        <Button type="submit" loading={save.isPending} disabled={!form.formState.isDirty}>
          {save.isPending ? tc("saving") : tc("save")}
        </Button>
      </div>
    </form>
  );
}
