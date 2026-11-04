"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/errors";

import {
  createTerm,
  deleteTerm,
  listTerms,
  termsKey,
  updateTerm,
  type AdminCategory,
  type TermKind,
} from "./api";

const KINDS: TermKind[] = ["categories", "materials", "techniques", "tags"];
const inputClass = "min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3 text-sm";

type Row = AdminCategory; // categories are a superset of the other term shapes

function AddTermForm({ kind, parents }: { kind: TermKind; parents: Row[] }) {
  const t = useTranslations("admin.terms");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [parent, setParent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () =>
      createTerm(kind, {
        name: name.trim(),
        ...(slug.trim() ? { slug: slug.trim() } : {}),
        ...(kind === "categories" ? { parent: parent ? Number(parent) : null } : {}),
      }),
    onSuccess: () => {
      setName("");
      setSlug("");
      setParent("");
      setError(null);
      void queryClient.invalidateQueries({ queryKey: termsKey(kind) });
    },
    onError: (e) => {
      if (!(e instanceof ApiError)) return;
      const first = Object.values(e.fieldErrors)[0]?.[0];
      setError(first ?? e.message);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) mutation.mutate();
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-4 rounded-[var(--radius-card)] border border-border/60 p-5">
      <label className="flex min-w-48 flex-1 flex-col gap-1 text-sm">
        {t("name")}
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
      </label>
      <label className="flex min-w-48 flex-1 flex-col gap-1 text-sm">
        <span>
          {t("slug")} <span className="text-muted">({tc("optional")})</span>
        </span>
        <input className={inputClass} dir="ltr" value={slug} onChange={(e) => setSlug(e.target.value)} maxLength={120} />
      </label>
      {kind === "categories" ? (
        <label className="flex min-w-48 flex-col gap-1 text-sm">
          {t("parent")}
          <select className={inputClass} value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">{t("noParent")}</option>
            {parents.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <Button type="submit" loading={mutation.isPending} disabled={!name.trim()}>
        {t("addNew")}
      </Button>
      {error ? (
        <p role="alert" className="w-full text-sm text-primary">
          {error}
        </p>
      ) : null}
    </form>
  );
}

function TermRow({ kind, term, parentName }: { kind: TermKind; term: Row; parentName?: string }) {
  const t = useTranslations("admin.terms");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(term.name);
  const [order, setOrder] = useState(String(term.sort_order ?? 0));
  const [confirming, setConfirming] = useState(false);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: termsKey(kind) });
  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => updateTerm(kind, term.id, body),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const remove = useMutation({ mutationFn: () => deleteTerm(kind, term.id), onSuccess: refresh });
  const error = update.error ?? remove.error;

  return (
    <li className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {editing ? (
          <div className="flex flex-wrap items-center gap-2">
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} aria-label={t("name")} />
            <input
              className={`${inputClass} w-24`}
              type="number"
              min={0}
              value={order}
              onChange={(e) => setOrder(e.target.value)}
              aria-label={t("order")}
            />
            <Button
              loading={update.isPending}
              onClick={() => update.mutate({ name: name.trim(), sort_order: Number(order) || 0 })}
            >
              {tc("save")}
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              {tc("cancel")}
            </Button>
          </div>
        ) : (
          <div>
            <p className={term.is_active ? "font-medium" : "font-medium text-muted line-through"}>
              {parentName ? <span className="text-muted">{parentName} · </span> : null}
              {term.name}
            </p>
            <p className="text-xs text-muted">
              <bdi dir="ltr">{term.slug}</bdi> · {t("usage", { count: term.usage_count })}
              {term.is_active ? "" : ` · ${t("inactive")}`}
            </p>
          </div>
        )}
        {!editing ? (
          <div className="flex flex-wrap gap-1">
            <Button variant="ghost" onClick={() => setEditing(true)}>
              {tc("edit")}
            </Button>
            <Button
              variant="ghost"
              loading={update.isPending}
              onClick={() => update.mutate({ is_active: !term.is_active })}
            >
              {term.is_active ? t("deactivate") : t("activate")}
            </Button>
            {term.usage_count === 0 ? (
              confirming ? (
                <>
                  <Button loading={remove.isPending} onClick={() => remove.mutate()}>
                    {tc("confirmDelete")}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirming(false)}>
                    {tc("cancel")}
                  </Button>
                </>
              ) : (
                <Button variant="ghost" onClick={() => setConfirming(true)}>
                  {tc("delete")}
                </Button>
              )
            ) : null}
          </div>
        ) : null}
      </div>
      {error instanceof ApiError ? (
        <p role="alert" className="text-sm text-primary">
          {error.message}
        </p>
      ) : null}
    </li>
  );
}

export function TermsManager() {
  const t = useTranslations("admin.terms");
  const tc = useTranslations("common");
  const [kind, setKind] = useState<TermKind>("categories");
  const terms = useQuery({ queryKey: termsKey(kind), queryFn: () => listTerms<Row>(kind) });
  const rows = terms.data ?? [];
  const byId = new Map(rows.map((r) => [r.id, r]));
  // Main categories first, each followed by its sub-categories.
  const ordered =
    kind === "categories"
      ? rows.filter((r) => !r.parent).flatMap((main) => [main, ...rows.filter((r) => r.parent === main.id)])
      : rows;

  return (
    <div className="flex flex-col gap-8">
      <div role="tablist" aria-label={t("title")} className="flex flex-wrap gap-2 border-b border-border/60">
        {KINDS.map((k) => (
          <button
            key={k}
            role="tab"
            type="button"
            aria-selected={k === kind}
            onClick={() => setKind(k)}
            className={[
              "-mb-px border-b-2 px-4 py-2 text-sm",
              k === kind ? "border-primary text-primary" : "border-transparent text-muted hover:text-text",
            ].join(" ")}
          >
            {t(`tabs.${k}`)}
          </button>
        ))}
      </div>
      <AddTermForm kind={kind} parents={rows.filter((r) => !r.parent)} />
      {terms.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {terms.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {terms.data && ordered.length === 0 ? <p className="text-muted">{t("empty")}</p> : null}
      {ordered.length ? (
        <ul className="divide-y divide-border/60 border-y border-border/60">
          {ordered.map((term) => (
            <TermRow
              key={term.id}
              kind={kind}
              term={term}
              parentName={term.parent ? byId.get(term.parent)?.name : undefined}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
