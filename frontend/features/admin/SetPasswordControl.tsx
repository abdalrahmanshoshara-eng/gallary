"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/errors";

import { setUserPassword } from "./api";

/** Super Admin sets a new password for someone else (forgotten password). Ends their sessions. */
export function SetPasswordControl({ userId }: { userId: string }) {
  const t = useTranslations("admin.users");
  const tc = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const save = useMutation({
    mutationFn: () => setUserPassword(userId, password),
    onSuccess: () => {
      setOpen(false);
      setPassword("");
    },
  });
  const error =
    save.error instanceof ApiError ? (save.error.fieldErrors.password?.join(" ") ?? save.error.message) : null;

  return (
    <div className="flex flex-col gap-2">
      <div>
        <Button variant="ghost" onClick={() => setOpen((v) => !v)}>
          {open ? tc("cancel") : t("setPassword")}
        </Button>
      </div>
      {open ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("newPassword")}
            <input
              type="password"
              dir="ltr"
              autoComplete="new-password"
              className="min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <Button loading={save.isPending} disabled={password.length === 0} onClick={() => save.mutate()}>
            {tc("save")}
          </Button>
        </div>
      ) : null}
      {save.isSuccess ? <p className="text-xs text-olive">{t("passwordSet")}</p> : null}
      {error ? (
        <p role="alert" className="text-xs text-primary">
          {error}
        </p>
      ) : null}
    </div>
  );
}
