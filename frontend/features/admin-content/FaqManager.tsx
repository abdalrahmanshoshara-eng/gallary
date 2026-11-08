"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { errorText } from "@/lib/forms";
import { Markdown } from "@/lib/markdown";

import { createFaq, deleteFaq, faqKey, listFaq, moveFaq, updateFaq, type AdminFaq } from "./api";
import { MoveButtons } from "./ContentTabs";

const input = "rounded-[var(--radius-control)] border border-border bg-white px-3 text-base focus:border-secondary focus:outline-none";

function FaqForm({ initial, onSave, onCancel, busy }: { initial?: AdminFaq; onSave: (v: { question: string; answer: string }) => void; onCancel: () => void; busy: boolean }) {
  const t = useTranslations("admin.content.faq");
  const [question, setQuestion] = useState(initial?.question ?? "");
  const [answer, setAnswer] = useState(initial?.answer ?? "");
  const [error, setError] = useState(false);
  const id = useId();
  return (
    <form
      noValidate
      className="flex flex-col gap-3 rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!question.trim() || !answer.trim()) return setError(true);
        onSave({ question: question.trim(), answer: answer.trim() });
      }}
    >
      <label className="flex flex-col gap-1 text-sm font-medium">
        {t("question")}
        <input className={`${input} min-h-11`} value={question} maxLength={300} onChange={(e) => setQuestion(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium">
        {t("answer")}
        <textarea className={`${input} min-h-28 py-2`} value={answer} aria-describedby={`${id}-hint`} onChange={(e) => setAnswer(e.target.value)} />
      </label>
      <span id={`${id}-hint`} className="-mt-2 text-xs text-muted">
        {t("answerHint")}
      </span>
      {error ? (
        <p role="alert" className="text-sm text-primary">
          {t("required")}
        </p>
      ) : null}
      <div className="flex gap-3">
        <Button type="submit" loading={busy}>
          {t("save")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

export function FaqManager() {
  const t = useTranslations("admin.content.faq");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [deleting, setDeleting] = useState<AdminFaq | null>(null);
  const faq = useQuery({ queryKey: faqKey, queryFn: listFaq });
  const set = (rows: AdminFaq[]) => queryClient.setQueryData(faqKey, rows);
  const mutate = useMutation({
    mutationFn: (fn: () => Promise<AdminFaq[]>) => fn(),
    onSuccess: (rows) => {
      set(rows);
      setEditing(null);
      setDeleting(null);
    },
  });

  if (faq.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (faq.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  const rows = faq.data as Required<AdminFaq>[];

  return (
    <div className="flex flex-col gap-6">
      {mutate.error ? <Alert tone="error">{errorText(mutate.error)}</Alert> : null}
      {editing === "new" ? (
        <FaqForm busy={mutate.isPending} onCancel={() => setEditing(null)} onSave={(v) => mutate.mutate(() => createFaq(v))} />
      ) : (
        <div>
          <Button onClick={() => setEditing("new")}>{t("add")}</Button>
        </div>
      )}
      {rows.length === 0 ? <p className="py-6 text-muted">{t("empty")}</p> : null}
      <ol className="flex flex-col gap-3">
        {rows.map((item, index) =>
          editing === item.id ? (
            <li key={item.id}>
              <FaqForm initial={item} busy={mutate.isPending} onCancel={() => setEditing(null)} onSave={(v) => mutate.mutate(() => updateFaq(item.id, v))} />
            </li>
          ) : (
            <li key={item.id} className={`rounded-[var(--radius-card)] border border-border/60 p-4 ${item.is_active ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-primary">{item.question}</p>
                  <Markdown source={item.answer} className="mt-2 gap-2 text-sm leading-7 text-muted" />
                </div>
                <MoveButtons
                  first={index === 0}
                  last={index === rows.length - 1}
                  busy={mutate.isPending}
                  upLabel={t("up", { question: item.question })}
                  downLabel={t("down", { question: item.question })}
                  onMove={(d) => mutate.mutate(() => moveFaq(item.id, d))}
                />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                <StatusBadge tone={item.is_active ? "success" : "closed"}>{item.is_active ? t("visible") : t("hidden")}</StatusBadge>
                <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => setEditing(item.id)}>
                  {t("edit")}
                </button>
                <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => mutate.mutate(() => updateFaq(item.id, { is_active: !item.is_active }))}>
                  {item.is_active ? t("hide") : t("show")}
                </button>
                <button type="button" className="text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setDeleting(item)}>
                  {t("delete")}
                </button>
              </div>
            </li>
          ),
        )}
      </ol>
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? t("deleteTitle", { question: deleting.question ?? "" }) : ""}
        confirmLabel={t("confirmDelete")}
        cancelLabel={t("cancel")}
        busy={mutate.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && mutate.mutate(() => deleteFaq(deleting.id))}
      >
        {t("deleteBody")}
      </ConfirmDialog>
    </div>
  );
}
