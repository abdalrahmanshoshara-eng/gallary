"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { errorText } from "@/lib/forms";

import { agreementsKey, createAgreement, endAgreement, getAgreements, type ArtistAgreements } from "./api";

const RATE = /^\d{1,3}(\.\d{1,2})?$/;
const dateText = (iso: string) => new Intl.DateTimeFormat("ar-SY-u-nu-latn", { dateStyle: "long", timeZone: "Asia/Damascus" }).format(new Date(iso));
const pct = (v: string) => String(Number(v));

/**
 * The artist's commission agreement (BR-701): the current rate in one line, its history,
 * and — for the Super Admin only — a new agreement or ending the current one. Every change
 * says that existing orders keep their rate (BR-703).
 */
export function AgreementsPanel({ artistId, artistName }: { artistId: string; artistName: string }) {
  const t = useTranslations("admin.agreements");
  const id = useId();
  const queryClient = useQueryClient();
  const [rate, setRate] = useState("");
  const [notes, setNotes] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [dialog, setDialog] = useState<"create" | "end" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const agreements = useQuery({ queryKey: agreementsKey(artistId), queryFn: () => getAgreements(artistId) });

  const done = (message: string) => (data: ArtistAgreements) => {
    queryClient.setQueryData(agreementsKey(artistId), data);
    void queryClient.invalidateQueries({ queryKey: ["admin", "listings"] });
    setDialog(null);
    setRate("");
    setNotes("");
    setNotice(message);
  };
  const create = useMutation({ mutationFn: () => createAgreement(artistId, rate.trim(), notes), onSuccess: done(t("saved")) });
  const end = useMutation({ mutationFn: () => endAgreement(artistId), onSuccess: done(t("ended")) });

  if (agreements.isPending) return <div className="h-24 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (agreements.isError) return <Alert tone="error">{errorText(agreements.error)}</Alert>;
  const a = agreements.data;
  const error = create.error ?? end.error;

  return (
    <section aria-labelledby={`${id}-title`} className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-border/60 p-5">
      <h2 id={`${id}-title`} className="text-lg font-medium text-primary">
        {t("title")}
      </h2>
      {notice ? <Alert tone="success">{notice}</Alert> : null}
      {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
      <p className={`text-sm ${a.active ? "font-medium text-text" : "text-muted"}`}>
        {a.active
          ? t("active", { rate: pct(a.active.commission_rate), date: dateText(a.active.effective_from) })
          : t("none", { rate: pct(a.default_commission_rate) })}
      </p>
      {a.active?.notes ? <p className="text-xs text-muted">{a.active.notes}</p> : null}

      {a.can_manage ? (
        <form
          noValidate
          className="flex flex-col gap-3 border-t border-border/50 pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            const ok = RATE.test(rate.trim()) && Number(rate) <= 100;
            setInvalid(!ok);
            if (ok) setDialog("create");
          }}
        >
          <p className="text-sm font-medium">{t("new")}</p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex w-28 flex-col gap-1 text-sm">
              {t("rate")}
              <input
                className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
                inputMode="decimal"
                dir="ltr"
                value={rate}
                aria-invalid={invalid || undefined}
                onChange={(e) => {
                  setRate(e.target.value);
                  setInvalid(false);
                }}
              />
            </label>
            <label className="flex min-w-40 flex-1 flex-col gap-1 text-sm">
              {t("notes")}
              <input className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </label>
          </div>
          {invalid ? (
            <p role="alert" className="text-sm text-primary">
              {t("invalid")}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" variant="secondary">
              {t("save")}
            </Button>
            {a.active ? (
              <Button variant="ghost" onClick={() => setDialog("end")}>
                {t("end")}
              </Button>
            ) : null}
          </div>
        </form>
      ) : (
        <p className="text-xs text-muted">{t("readOnly")}</p>
      )}

      {a.history.length ? (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted hover:text-primary">{t("history")}</summary>
          <ul className="mt-2 flex flex-col gap-1">
            {a.history.map((h) => (
              <li key={h.id} className="flex justify-between gap-4 text-xs">
                <span>{t("period", { from: dateText(h.effective_from), to: h.effective_to ? dateText(h.effective_to) : "—" })}</span>
                <span className="tabular-nums">{pct(h.commission_rate)}%</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <ConfirmDialog
        open={dialog === "create"}
        title={t("confirmTitle", { rate: pct(rate || "0"), name: artistName })}
        confirmLabel={t("save")}
        cancelLabel={t("cancel")}
        busy={create.isPending}
        onCancel={() => setDialog(null)}
        onConfirm={() => create.mutate(undefined, { onError: () => setDialog(null) })}
      >
        {a.active ? <p>{t("confirmReplace", { current: pct(a.active.commission_rate) })}</p> : null}
        <p className="mt-1">{t("confirmScope")}</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === "end"}
        title={t("endTitle", { name: artistName })}
        confirmLabel={t("end")}
        cancelLabel={t("cancel")}
        busy={end.isPending}
        onCancel={() => setDialog(null)}
        onConfirm={() => end.mutate(undefined, { onError: () => setDialog(null) })}
      >
        {t("endBody", { rate: pct(a.default_commission_rate) })}
      </ConfirmDialog>
    </section>
  );
}
