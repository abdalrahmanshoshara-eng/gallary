"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import { getRequest, requestKey, requestsKey, withdrawRequest, type RequestStatus } from "./api";
import { RequestForm } from "./RequestForm";
import { requestTone } from "./tone";

const FLOW: RequestStatus[] = ["submitted", "under_review", "negotiation", "approved"];

function Timeline({ status, history }: { status: RequestStatus; history: { status: string; at: string }[] }) {
  const t = useTranslations("auctionRequests");
  const reached = new Map(history.map((h) => [h.status, h.at]));
  const off = status === "rejected" || status === "withdrawn";
  const current = FLOW.indexOf(status === "needs_more_info" ? "under_review" : status);
  return (
    <ol aria-label={t("timeline")} className="grid grid-cols-4 gap-2">
      {FLOW.map((step, index) => {
        const done = !off && index <= current;
        return (
          <li key={step} className="flex flex-col gap-2" aria-current={index === current && !off ? "step" : undefined}>
            <span className={`h-1.5 rounded-full ${done ? (index === current ? "bg-secondary" : "bg-olive") : "bg-surface"}`} />
            <span className={`text-xs ${done ? "text-text" : "text-muted"}`}>{t(`status.${step}`)}</span>
            {reached.get(step) ? <span className="text-[11px] text-muted">{formatDateTime(reached.get(step)!)}</span> : null}
          </li>
        );
      })}
    </ol>
  );
}

export function RequestView({ id, justSubmitted }: { id: string; justSubmitted: boolean }) {
  const t = useTranslations("auctionRequests");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [updated, setUpdated] = useState(false);
  const request = useQuery({ queryKey: requestKey(id), queryFn: () => getRequest(id) });
  const withdraw = useMutation({
    mutationFn: () => withdrawRequest(id),
    onSuccess: (data) => {
      queryClient.setQueryData(requestKey(id), data);
      void queryClient.invalidateQueries({ queryKey: requestsKey });
      setConfirming(false);
    },
  });

  if (request.isPending) return <div className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (request.isError) {
    const missing = request.error instanceof ApiError && request.error.status === 404;
    return (
      <Alert tone="error">
        {missing ? t("notFound") : tc("loadError")}{" "}
        <Link href="/auction-requests" className="underline">
          {t("all")}
        </Link>
      </Alert>
    );
  }
  const r = request.data;
  const history = r.history as { status: string; at: string }[];

  if (editing) {
    return (
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-semibold text-primary">{t("edit")}</h1>
        {r.messages.length ? <Alert tone="info">{r.messages.at(-1)!.body}</Alert> : null}
        <RequestForm
          existing={r}
          onDone={() => {
            setEditing(false);
            setUpdated(r.status === "needs_more_info");
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-primary md:text-3xl">{r.work_title}</h1>
          <p className="mt-1 text-sm text-muted">{t("submittedOn", { date: formatDateTime(r.created_at) })}</p>
        </div>
        <StatusBadge tone={requestTone(r.status)}>{t(`status.${r.status}`)}</StatusBadge>
      </header>

      {justSubmitted && r.status === "submitted" ? <Alert tone="success">{t("submitted")}</Alert> : null}
      {updated && r.status === "under_review" ? <Alert tone="success">{t("updated")}</Alert> : null}
      {withdraw.isSuccess ? <Alert tone="success">{t("withdrawn")}</Alert> : null}
      {withdraw.error ? <Alert tone="error">{errorText(withdraw.error)}</Alert> : null}

      <section aria-labelledby="request-state" className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-5">
        <h2 id="request-state" className="sr-only">
          {t("timeline")}
        </h2>
        <p className={`text-sm ${r.status === "needs_more_info" ? "font-medium text-primary" : "text-text"}`}>{t(`statusHelp.${r.status}`)}</p>
        <div className="mt-5">
          <Timeline status={r.status} history={history} />
        </div>
        {r.can_edit || r.auction_id ? (
          <div className="mt-6 flex flex-wrap gap-3">
            {r.can_edit ? <Button onClick={() => setEditing(true)}>{t("edit")}</Button> : null}
            {r.auction_id ? (
              <Link
                href={`/auctions/${r.auction_id}`}
                className="inline-flex min-h-11 items-center rounded-[var(--radius-control)] bg-primary px-6 text-sm font-medium text-on-primary hover:bg-primary/90"
              >
                {t("viewAuction")}
              </Link>
            ) : null}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="request-messages">
        <h2 id="request-messages" className="mb-3 text-lg font-medium text-primary">
          {t("messages")}
        </h2>
        {r.messages.length === 0 ? (
          <p className="text-sm text-muted">{t("noMessages")}</p>
        ) : (
          <ol className="flex flex-col gap-3">
            {r.messages.map((m, index) => (
              <li key={index} className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-4">
                <p className="whitespace-pre-line text-sm leading-7">{m.body}</p>
                <time dateTime={m.created_at} className="mt-2 block text-xs text-muted">
                  {formatDateTime(m.created_at)}
                </time>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section aria-labelledby="request-details">
        <h2 id="request-details" className="mb-3 text-lg font-medium text-primary">
          {t("details")}
        </h2>
        {r.images.length ? (
          <ul className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-5">
            {r.images.map((image) => (
              <li key={image.id} className="aspect-square overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
                {image.variants.length ? <ResponsiveImage image={image} alt="" sizes="8rem" /> : null}
              </li>
            ))}
          </ul>
        ) : null}
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
                <dt className="text-muted">{t(`fields.${key}`)}</dt>
                <dd className="whitespace-pre-line sm:col-span-2">{value}</dd>
              </div>
            ))}
        </dl>
      </section>

      {r.can_withdraw ? (
        <div className="border-t border-border/60 pt-4">
          <button type="button" className="text-sm text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setConfirming(true)}>
            {t("withdraw")}
          </button>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirming}
        title={t("withdrawTitle", { title: r.work_title })}
        confirmLabel={t("withdrawConfirm")}
        cancelLabel={t("keep")}
        busy={withdraw.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() => withdraw.mutate()}
      >
        {t("withdrawBody")}
      </ConfirmDialog>
    </div>
  );
}
