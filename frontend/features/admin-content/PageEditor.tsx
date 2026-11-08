"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/formatters/datetime";
import { errorText } from "@/lib/forms";
import { Markdown } from "@/lib/markdown";

import { getPage, getVersion, pageKey, pagesKey, publishPage, saveDraft, type AdminPage } from "./api";

const input = "rounded-[var(--radius-control)] border border-border bg-white px-4 text-base text-text focus:border-secondary focus:outline-none";

function Versions({ page }: { page: AdminPage }) {
  const t = useTranslations("admin.content.pages");
  const [open, setOpen] = useState<number | null>(null);
  const version = useQuery({
    queryKey: ["admin", "content", "version", page.slug, open],
    queryFn: () => getVersion(page.slug, open!),
    enabled: open !== null,
  });
  return (
    <section aria-labelledby="versions" className="flex flex-col gap-3">
      <h2 id="versions" className="text-lg font-medium text-primary">
        {t("versions")}
      </h2>
      {page.versions.length === 0 ? <p className="text-sm text-muted">{t("noVersions")}</p> : null}
      <ol className="flex flex-col gap-2">
        {page.versions.map((v) => (
          <li key={v.number} className="rounded-[var(--radius-control)] border border-border/60 p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                {t("versionLine", {
                  number: v.number,
                  code: v.code,
                  date: formatDateTime(v.published_at),
                  by: v.published_by ? t("by", { name: v.published_by }) : "",
                })}
                {page.published?.number === v.number ? <span className="ms-2 rounded-full bg-olive/15 px-2 py-0.5 text-xs text-olive">{t("current")}</span> : null}
              </span>
              <button type="button" className="text-xs text-primary underline-offset-4 hover:underline" aria-expanded={open === v.number} onClick={() => setOpen(open === v.number ? null : v.number)}>
                {open === v.number ? t("hideVersion") : t("showVersion")}
              </button>
            </div>
            {open === v.number && version.data ? (
              <div className="mt-3 border-t border-border/50 pt-3">
                <p className="mb-2 font-medium">{version.data.title}</p>
                <Markdown source={version.data.body} className="text-sm" />
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

/**
 * Edit a page as a private draft with a live preview, then publish it as a new immutable
 * version (F-CMS-01). For the deposit policy the confirmation states its effect on checkout.
 */
export function PageEditor({ slug }: { slug: string }) {
  const t = useTranslations("admin.content.pages");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const page = useQuery({ queryKey: pageKey(slug), queryFn: () => getPage(slug) });
  const [draft, setDraft] = useState<{ title: string; body: string } | null>(null);
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const apply = (data: AdminPage, message: string) => {
    queryClient.setQueryData(pageKey(slug), data);
    void queryClient.invalidateQueries({ queryKey: pagesKey });
    setDraft(null);
    setNotice(message);
  };
  const save = useMutation({
    mutationFn: () => saveDraft(slug, draft!.title, draft!.body),
    onSuccess: (data) => apply(data, t("saved")),
  });
  const publish = useMutation({
    mutationFn: () => publishPage(slug),
    onSuccess: (data) => {
      apply(data, t("published", { number: data.published?.number ?? 0 }));
      setConfirming(false);
    },
    onError: () => setConfirming(false),
  });

  if (page.isPending) return <div className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (page.isError) return <Alert tone="error">{errorText(page.error)}</Alert>;
  const p = page.data;
  const title = draft?.title ?? p.draft_title;
  const body = draft?.body ?? p.draft_body;
  const dirty = draft !== null && (draft.title !== p.draft_title || draft.body !== p.draft_body);
  const editable = p.can_edit;
  const isPolicy = slug === "deposit-policy";

  const preview = (
    <div className="min-h-64 rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-5">
      {title || body ? (
        <>
          <p className="mb-4 text-2xl font-semibold text-primary">{title}</p>
          <Markdown source={body} className="text-sm" />
        </>
      ) : (
        <p className="text-sm text-muted">{t("previewEmpty")}</p>
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/admin/content" className="text-sm text-muted hover:text-secondary">
            {t("back")}
          </Link>
          <h2 className="mt-1 text-2xl font-semibold text-primary">{p.label}</h2>
          <p className="mt-1 text-xs text-muted">
            {p.published
              ? t("status.published", { number: p.published.number, date: formatDateTime(p.published.published_at) })
              : t("status.unpublished")}
            {p.draft_updated_at
              ? ` · ${t("draftBy", { date: formatDateTime(p.draft_updated_at), by: p.draft_updated_by ? t("by", { name: p.draft_updated_by }) : "" })}`
              : ""}
          </p>
        </div>
        {p.published ? (
          <Link href={`/${slug}` as "/about"} target="_blank" className="text-sm text-primary underline-offset-4 hover:underline">
            {t("publicLink")}
          </Link>
        ) : null}
      </header>

      {notice ? <Alert tone="success">{notice}</Alert> : null}
      {save.error ? <Alert tone="error">{errorText(save.error)}</Alert> : null}
      {publish.error ? <Alert tone="error">{errorText(publish.error)}</Alert> : null}
      {!editable ? <Alert tone="info">{t("readOnly")}</Alert> : null}

      {editable ? (
        <>
          <div className="flex gap-2 lg:hidden" role="tablist">
            {(["edit", "preview"] as const).map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-full border px-4 py-1.5 text-sm ${mode === m ? "border-primary bg-primary text-on-primary" : "border-border"}`}
              >
                {m === "edit" ? t("editTab") : t("preview")}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
            <div className={`flex flex-col gap-4 ${mode === "preview" ? "hidden lg:flex" : ""}`}>
              <label className="flex flex-col gap-2 text-sm font-medium">
                {t("titleField")}
                <input className={`${input} min-h-11`} value={title} maxLength={200} onChange={(e) => setDraft({ title: e.target.value, body })} />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium">
                {t("bodyField")}
                <textarea className={`${input} min-h-96 py-3 leading-7`} value={body} onChange={(e) => setDraft({ title, body: e.target.value })} />
              </label>
              <p className="text-xs text-muted" dir="auto">
                {t("syntax")}
              </p>
            </div>
            <div className={mode === "edit" ? "hidden lg:block" : ""}>
              <p className="mb-2 hidden text-sm font-medium lg:block">{t("preview")}</p>
              {preview}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-6">
            <Button variant="secondary" loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
              {t("saveDraft")}
            </Button>
            <Button disabled={dirty || !p.unpublished_changes} onClick={() => setConfirming(true)}>
              {t("publish")}
            </Button>
            <span className="text-xs text-muted">{dirty ? t("unsaved") : !p.unpublished_changes ? t("nothingNew") : null}</span>
          </div>
        </>
      ) : p.published ? (
        <div className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-5">
          <p className="mb-4 text-2xl font-semibold text-primary">{p.published.title}</p>
          <Markdown source={p.published.body} className="text-sm" />
        </div>
      ) : null}

      <Versions page={p} />

      <ConfirmDialog
        open={confirming}
        title={t("publishTitle", { title: p.draft_title || p.label })}
        confirmLabel={t("publish")}
        cancelLabel={tc("cancel")}
        busy={publish.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() => publish.mutate()}
      >
        <p>{t("publishBody")}</p>
        {isPolicy ? <p className="mt-2 font-medium text-text">{t("publishPolicy")}</p> : null}
      </ConfirmDialog>
    </div>
  );
}
