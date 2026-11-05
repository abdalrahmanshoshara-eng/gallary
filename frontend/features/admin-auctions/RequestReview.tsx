"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { requestTone } from "@/features/auction-requests/tone";
import { Link } from "@/i18n/navigation";
import { apiFetch } from "@/lib/api/client";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";
import { isCatalogEditor } from "@/lib/auth/types";
import type { CategoryNode } from "@/lib/catalog/types";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import {
  addRequestNote,
  adminRequestKey,
  createRequestArtwork,
  getAdminRequest,
  setRequestCommission,
  transitionRequest,
  type AdminAuctionRequest,
} from "./api";

type Transition = "under_review" | "needs_more_info" | "negotiation" | "rejected" | "approved";
const TRANSITIONS: Transition[] = ["under_review", "negotiation", "needs_more_info", "approved", "rejected"];
const field = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";

function CommissionForm({ request, onSaved }: { request: AdminAuctionRequest; onSaved: (r: AdminAuctionRequest) => void }) {
  const t = useTranslations("admin.auctionRequests");
  const [rate, setRate] = useState(request.agreed_commission_rate ? String(Number(request.agreed_commission_rate)) : "");
  const [note, setNote] = useState("");
  const valid = /^\d{1,3}(\.\d{1,2})?$/.test(rate.trim()) && Number(rate) <= 100;
  const save = useMutation({ mutationFn: () => setRequestCommission(request.id, rate.trim(), note), onSuccess: onSaved });
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <p className="text-sm font-medium">{t("commission")}</p>
      {request.agreed_commission_rate !== null && request.commission_agreed_at ? (
        <p className="text-sm text-olive">
          {t("commissionAgreed", { rate: String(Number(request.agreed_commission_rate)), date: formatDateTime(request.commission_agreed_at) })}
        </p>
      ) : (
        <p className="text-xs text-muted">{t("commissionNeeded")}</p>
      )}
      {save.error ? <Alert tone="error">{errorText(save.error)}</Alert> : null}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex w-32 flex-col gap-1 text-sm">
          {t("commissionRate")}
          <input className={field} inputMode="decimal" dir="ltr" value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label className="flex min-w-48 flex-1 flex-col gap-1 text-sm">
          {t("commissionNote")}
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <Button type="submit" variant="secondary" loading={save.isPending} disabled={!valid}>
          {t("saveCommission")}
        </Button>
      </div>
    </form>
  );
}

function ArtworkStep({ request, onSaved }: { request: AdminAuctionRequest; onSaved: (r: AdminAuctionRequest) => void }) {
  const t = useTranslations("admin.auctionRequests");
  const [category, setCategory] = useState("");
  const categories = useQuery({ queryKey: ["catalog", "categories"], queryFn: () => apiFetch<CategoryNode[]>("/catalog/categories") });
  const create = useMutation({ mutationFn: () => createRequestArtwork(request.id, category), onSuccess: onSaved });
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">{t("createArtworkBody")}</p>
      {create.error ? <Alert tone="error">{errorText(create.error)}</Alert> : null}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-56 flex-col gap-1 text-sm">
          {t("category")}
          <select className={field} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">—</option>
            {categories.data?.map((c) => (
              <optgroup key={c.slug} label={c.name}>
                <option value={c.slug}>{c.name}</option>
                {c.children.map((child) => (
                  <option key={child.slug} value={child.slug}>
                    {child.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <Button loading={create.isPending} disabled={!category} onClick={() => create.mutate()}>
          {t("createArtwork")}
        </Button>
      </div>
    </div>
  );
}

/**
 * One auction request: everything the reviewer needs on one screen, and only the moves the
 * request's state allows (computed by the server). Approval stays off until the platform's
 * share is recorded (BR-606).
 */
export function RequestReview({ id }: { id: string }) {
  const t = useTranslations("admin.auctionRequests");
  const tr = useTranslations("auctionRequests");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const [dialog, setDialog] = useState<Transition | null>(null);
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");
  const [visibility, setVisibility] = useState<"internal" | "customer">("internal");
  const [notice, setNotice] = useState<string | null>(null);
  const request = useQuery({ queryKey: adminRequestKey(id), queryFn: () => getAdminRequest(id) });

  const apply = (text?: string) => (result: AdminAuctionRequest) => {
    queryClient.setQueryData(adminRequestKey(id), result);
    void queryClient.invalidateQueries({ queryKey: ["admin", "auction-requests"] });
    setNotice(text ?? null);
  };
  const move = useMutation({
    mutationFn: (to: Transition) => transitionRequest(id, to, message),
    onSuccess: (result) => {
      apply()(result);
      setDialog(null);
      setMessage("");
    },
  });
  const addNote = useMutation({
    mutationFn: () => addRequestNote(id, note, visibility),
    onSuccess: (result) => {
      apply()(result);
      setNote("");
    },
  });

  if (request.isPending) return <div className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (request.isError) return <Alert tone="error">{errorText(request.error)}</Alert>;
  const r = request.data;
  const actions = new Set(r.actions);
  const transitions = TRANSITIONS.filter((to) => actions.has(to));
  const messageRequired = dialog === "needs_more_info";

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-primary md:text-3xl">{r.work_title}</h1>
          <p className="mt-1 text-sm text-muted">
            {r.customer} · <bdi dir="ltr">{r.contact_phone}</bdi>
            {r.customer_email ? (
              <>
                {" · "}
                <bdi dir="ltr">{r.customer_email}</bdi>
              </>
            ) : null}
          </p>
          <p className="text-xs text-muted">{tr("submittedOn", { date: formatDateTime(r.created_at) })}</p>
        </div>
        <StatusBadge tone={requestTone(r.status)}>{tr(`status.${r.status}`)}</StatusBadge>
      </header>

      {notice ? <Alert tone="success">{notice}</Alert> : null}

      <section aria-labelledby="next-steps" className="flex flex-col gap-5 rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-5">
        <h2 id="next-steps" className="text-lg font-medium text-primary">
          {t("nextSteps")}
        </h2>
        {move.error ? <Alert tone="error">{errorText(move.error)}</Alert> : null}
        {transitions.length ? (
          <div className="flex flex-wrap gap-3">
            {transitions.map((to) => (
              <Button
                key={to}
                variant={to === "approved" || (to === "under_review" && r.status === "submitted") ? "primary" : to === "rejected" ? "ghost" : "secondary"}
                onClick={() => setDialog(to)}
              >
                {t(`actions.${to}`)}
              </Button>
            ))}
          </div>
        ) : null}
        {actions.has("set_commission") ? <CommissionForm request={r} onSaved={apply(t("commissionSaved"))} /> : null}
        {actions.has("create_artwork") ? <ArtworkStep request={r} onSaved={apply(t("artworkCreated"))} /> : null}
        {actions.has("create_auction") && r.artwork_id ? (
          <div className="flex flex-wrap items-center gap-4">
            <Link
              href={`/admin/auctions/new?request=${r.id}`}
              className="inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary hover:bg-primary/90"
            >
              {t("createAuction")}
            </Link>
            {isCatalogEditor(user ?? null) ? (
              <Link href={`/admin/artworks/${r.artwork_id}`} className="text-sm text-primary underline-offset-4 hover:underline">
                {t("editArtwork")}
              </Link>
            ) : null}
          </div>
        ) : null}
        {r.auction_id ? (
          <p className="text-sm text-olive">
            {t("done")}{" "}
            <Link href={`/admin/auctions/${r.auction_id}`} className="font-medium underline">
              {t("viewAuction")}
            </Link>
          </p>
        ) : null}
        {!r.actions.length && !r.auction_id ? <p className="text-sm text-muted">{t("final")}</p> : null}
      </section>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-labelledby="request-details" className="flex flex-col gap-4">
          <h2 id="request-details" className="text-lg font-medium text-primary">
            {tr("details")}
          </h2>
          {r.images.length ? (
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4">
              {r.images.map((image) => (
                <li key={image.id} className="aspect-square overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
                  {image.variants.length ? (
                    <a href={image.variants.at(-1)!.url} target="_blank" rel="noopener noreferrer">
                      <ResponsiveImage image={image} alt="" sizes="10rem" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">{t("noImages")}</p>
          )}
          <dl className="text-sm">
            {(
              [
                ["artist_name", r.artist_name],
                ["work_description", r.work_description],
                ["category_hint", r.category_hint],
                ["dimensions_text", r.dimensions_text],
                ["year_text", r.year_text],
                ["expected_price", r.expected_price ? formatUsd(r.expected_price) : ""],
                ["artist_info", r.artist_info],
                ["customer_notes", r.customer_notes],
              ] as const
            )
              .filter(([, value]) => value)
              .map(([key, value]) => (
                <div key={key} className="grid gap-1 border-b border-border/40 py-3 sm:grid-cols-3 sm:gap-4">
                  <dt className="text-muted">{tr(`fields.${key}`)}</dt>
                  <dd className="whitespace-pre-line sm:col-span-2">{value}</dd>
                </div>
              ))}
          </dl>
        </section>

        <aside aria-labelledby="notes" className="flex flex-col gap-4">
          <h2 id="notes" className="text-lg font-medium text-primary">
            {t("notes")}
          </h2>
          {r.notes.length === 0 ? <p className="text-sm text-muted">{t("noNotes")}</p> : null}
          <ol className="flex flex-col gap-3">
            {r.notes.map((n, index) => (
              <li
                key={index}
                className={`rounded-[var(--radius-card)] border p-3 text-sm ${n.visibility === "customer" ? "border-secondary/50 bg-secondary/5" : "border-border/60"}`}
              >
                <p className="text-xs text-muted">
                  {t(`visibility.${n.visibility as "internal"}`)} · {n.author ?? ""} · {formatDateTime(n.created_at)}
                </p>
                <p className="mt-1 whitespace-pre-line">{n.body}</p>
              </li>
            ))}
          </ol>
          <form
            className="flex flex-col gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (note.trim()) addNote.mutate();
            }}
          >
            {addNote.error ? <Alert tone="error">{errorText(addNote.error)}</Alert> : null}
            <label className="flex flex-col gap-1 text-sm">
              {t("noteBody")}
              <textarea className="min-h-20 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2" value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <select className={field} value={visibility} onChange={(e) => setVisibility(e.target.value as typeof visibility)} aria-label={tc("status")}>
                <option value="internal">{t("visibility.internal")}</option>
                <option value="customer">{t("visibility.customer")}</option>
              </select>
              <Button type="submit" variant="secondary" loading={addNote.isPending} disabled={!note.trim()}>
                {t("addNote")}
              </Button>
            </div>
          </form>
        </aside>
      </div>

      <ConfirmDialog
        open={dialog !== null}
        title={dialog ? t(`actionTitles.${dialog}`) : ""}
        confirmLabel={dialog ? t(`actions.${dialog}`) : ""}
        cancelLabel={tc("cancel")}
        busy={move.isPending}
        confirmDisabled={messageRequired && !message.trim()}
        onCancel={() => {
          setDialog(null);
          setMessage("");
        }}
        onConfirm={() => dialog && move.mutate(dialog)}
      >
        <label className="flex flex-col gap-1 text-sm text-text">
          {messageRequired ? t("messageLabel") : t("messageOptional")}
          <textarea
            className="min-h-24 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required={messageRequired}
          />
        </label>
        {messageRequired ? <p className="mt-1 text-xs">{t("messageRequired")}</p> : null}
      </ConfirmDialog>
    </div>
  );
}
