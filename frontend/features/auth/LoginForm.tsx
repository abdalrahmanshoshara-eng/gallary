"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { currentUserKey } from "@/lib/auth/useCurrentUser";

import { requestOtp, verifyOtp, type OtpRequested } from "./api";
import { codeSchema, phoneSchema, type CodeInput, type PhoneInput } from "./schemas";
import { useCountdown } from "./useCountdown";

function retryAfter(error: unknown): number | null {
  if (!(error instanceof ApiError) || typeof error.details !== "object" || error.details === null) return null;
  const value = (error.details as Record<string, unknown>)["retry_after_seconds"];
  return typeof value === "number" ? value : null;
}

function remainingAttempts(error: unknown): number | null {
  if (!(error instanceof ApiError) || typeof error.details !== "object" || error.details === null) return null;
  const value = (error.details as Record<string, unknown>)["remaining_attempts"];
  return typeof value === "number" ? value : null;
}

export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [sent, setSent] = useState<OtpRequested | null>(null);
  const [resendAt, setResendAt] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const resendIn = useCountdown(resendAt);

  const phoneForm = useForm<PhoneInput>({ resolver: zodResolver(phoneSchema), defaultValues: { phone: "" } });
  const codeForm = useForm<CodeInput>({ resolver: zodResolver(codeSchema), defaultValues: { code: "" } });

  const send = useMutation({
    mutationFn: (phone: string) => requestOtp(phone),
    onMutate: () => setFormError(null),
    onSuccess: (result) => {
      setSent(result);
      setResendAt(Date.now() + result.resend_after_seconds * 1000);
      codeForm.reset({ code: "" });
    },
    onError: (error) => {
      const wait = retryAfter(error);
      if (wait !== null) setResendAt(Date.now() + wait * 1000);
      if (error instanceof ApiError && error.code === "INVALID_PHONE") {
        phoneForm.setError("phone", { message: error.message });
        return;
      }
      setFormError(error instanceof ApiError ? error.message : null);
    },
  });

  const verify = useMutation({
    mutationFn: ({ phone, code }: { phone: string; code: string }) => verifyOtp(phone, code),
    onMutate: () => setFormError(null),
    onSuccess: (result) => {
      queryClient.setQueryData(currentUserKey, result.user);
      router.replace(next);
      router.refresh();
    },
    onError: (error) => {
      if (!(error instanceof ApiError)) return;
      const remaining = remainingAttempts(error);
      const extra = remaining ? ` ${t("remainingAttempts", { count: remaining })}` : "";
      codeForm.setError("code", { message: `${error.message}${extra}` });
      if (error.code === "OTP_EXPIRED") setResendAt(null);
    },
  });

  if (!sent) {
    return (
      <form
        noValidate
        className="flex flex-col gap-6"
        onSubmit={phoneForm.handleSubmit((values) => send.mutate(phoneSchema.parse(values).phone))}
      >
        {formError ? <Alert tone="error">{formError}</Alert> : null}
        <Field
          label={t("phoneLabel")}
          hint={t("phoneHint")}
          type="tel"
          dir="ltr"
          autoComplete="tel"
          inputMode="tel"
          error={phoneForm.formState.errors.phone?.message && translateError(t, phoneForm.formState.errors.phone.message)}
          {...phoneForm.register("phone")}
        />
        <p className="text-sm text-muted">{t("whatsappNotice")}</p>
        <Button type="submit" loading={send.isPending} disabled={resendIn > 0}>
          {send.isPending ? t("sending") : resendIn > 0 ? t("resendIn", { seconds: resendIn }) : t("sendCode")}
        </Button>
      </form>
    );
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-6"
      onSubmit={codeForm.handleSubmit((values) =>
        verify.mutate({ phone: sent.phone, code: codeSchema.parse(values).code }),
      )}
    >
      <div>
        <h2 className="text-xl font-medium text-primary">{t("codeTitle")}</h2>
        <p className="mt-2 text-sm text-muted">
          {t.rich("codeSentTo", { number: sent.phone, phone: (chunks) => <bdi dir="ltr">{chunks}</bdi> })}
        </p>
      </div>
      {formError ? <Alert tone="error">{formError}</Alert> : null}
      <Field
        label={t("codeLabel")}
        dir="ltr"
        autoComplete="one-time-code"
        inputMode="numeric"
        maxLength={6}
        className="tracking-[0.5em]"
        error={codeForm.formState.errors.code?.message && translateError(t, codeForm.formState.errors.code.message)}
        {...codeForm.register("code")}
      />
      <Button type="submit" loading={verify.isPending}>
        {verify.isPending ? t("verifying") : t("verify")}
      </Button>
      <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
        <button
          type="button"
          className="text-secondary underline-offset-4 hover:underline disabled:text-muted disabled:no-underline"
          disabled={resendIn > 0 || send.isPending}
          onClick={() => send.mutate(sent.phone)}
        >
          {resendIn > 0 ? t("resendIn", { seconds: resendIn }) : t("resend")}
        </button>
        <button
          type="button"
          className="text-muted underline-offset-4 hover:underline"
          onClick={() => {
            setSent(null);
            setFormError(null);
          }}
        >
          {t("changePhone")}
        </button>
      </div>
    </form>
  );
}

/** Client-side Zod messages are translation keys; server messages are already Arabic. */
function translateError(t: ReturnType<typeof useTranslations<"auth">>, message: string): string {
  return message === "phoneInvalid" || message === "codeInvalid" ? t(message) : message;
}
