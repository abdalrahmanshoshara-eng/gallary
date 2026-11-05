"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Icon } from "@/components/ui/Icon";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";
import { formatUsd } from "@/lib/formatters/money";

import { placeBid, type AuctionDetail, type BidRejection } from "./api";
import { depositFor, durationText, percentText } from "./format";
import { normalizeAmount, quickAmounts, type AuctionState, type Phase } from "./live";

const primaryLink =
  "inline-flex min-h-12 w-full items-center justify-center rounded-[var(--radius-control)] bg-primary px-6 font-medium text-on-primary transition-colors duration-300 ease-calm hover:bg-primary/90";

type Feedback =
  | { tone: "success"; text: string }
  | { tone: "error"; text: string }
  | { tone: "unsure"; text: string };

function newKey() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`.replace(".", "");
}

/**
 * The bidding action, adapted to who is looking and to the auction's phase. One primary
 * action ("زايد"); every bid is confirmed explicitly because it is binding. The server is
 * the only judge: the panel pre-checks the minimum, then shows the server's verdict in
 * plain language and keeps the field in step with the new minimum.
 */
export function BidPanel({
  detail,
  state,
  phase,
  onAccepted,
  onStale,
}: {
  detail: AuctionDetail;
  state: AuctionState;
  phase: Phase;
  onAccepted: (state: AuctionState) => void;
  onStale: () => void;
}) {
  const t = useTranslations("auctions.bid");
  const ta = useTranslations("auctions");
  const { data: user, isPending } = useCurrentUser();
  const inputId = useId();
  // The viewer's draft amount, remembered with the minimum it was typed against: when
  // someone else raises the minimum above it, the field shows the new minimum instead.
  const [draft, setDraft] = useState<{ value: string; minimum: string } | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  // One key per bid attempt: a retry after a network failure re-sends the same key, so the
  // server returns the first result instead of recording a second bid (BR-507a).
  const attempt = useRef<{ amount: string; key: string } | null>(null);

  const minimum = state.minimum_next_bid;
  const draftAmount = draft ? normalizeAmount(draft.value) : null;
  const amount =
    draft && (draft.minimum === minimum || (draftAmount !== null && Number(draftAmount) >= Number(minimum))) ? draft.value : minimum;
  const setAmount = (value: string) => setDraft({ value, minimum });

  const bid = useMutation({
    mutationFn: placeBid,
    onSuccess: (result) => {
      attempt.current = null;
      setDraft(null);
      setFeedback({ tone: "success", text: t("accepted") });
      onAccepted(result.state);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "BID_REJECTED") {
        attempt.current = null;
        const details = (error.details ?? {}) as { reason?: BidRejection; minimum_next_bid?: string };
        const reason = details.reason ?? "not_open";
        if (details.minimum_next_bid) setDraft({ value: details.minimum_next_bid, minimum: details.minimum_next_bid });
        setFeedback({ tone: "error", text: t(`rejected.${reason}`, { amount: formatUsd(details.minimum_next_bid ?? minimum) }) });
        onStale();
        return;
      }
      if (error instanceof ApiError && error.status !== 0 && error.status < 500) {
        attempt.current = null;
        setFeedback({ tone: "error", text: error.message });
        return;
      }
      // Network failure or server error: the bid may or may not have been recorded.
      setFeedback({ tone: "unsure", text: t("unsure") });
    },
  });

  if (isPending) return <div className="h-32 animate-pulse rounded-[var(--radius-control)] bg-surface/60" aria-hidden />;

  const paymentWindow = durationText(detail.winner_payment_window_sec, ta);
  const percent = percentText(detail.winner_deposit_percent);

  if (phase === "closing") {
    return (
      <p className="flex items-center gap-3 rounded-[var(--radius-control)] bg-surface/70 px-4 py-4 text-sm text-primary" role="status">
        <span className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent motion-reduce:animate-none" aria-hidden />
        {t("closing")}
      </p>
    );
  }
  if (phase !== "live" && phase !== "upcoming") return null;

  if (!user) {
    return (
      <div className="flex flex-col gap-2">
        <Link href={{ pathname: "/login", query: { next: `/auctions/${detail.id}` } }} className={primaryLink}>
          {t("loginToBid")}
        </Link>
        <p className="text-xs text-muted">{phase === "upcoming" ? t("upcoming") : t("loginHint")}</p>
      </div>
    );
  }
  if (user.is_staff) return <p className="text-sm text-muted">{t("staffNote")}</p>;
  if (phase === "upcoming") return <p className="text-sm text-muted">{t("upcoming")}</p>;

  const me = state.me;
  if (me?.is_highest) {
    return (
      <div className="flex flex-col gap-3">
        {feedback?.tone === "success" ? <Alert tone="success">{feedback.text}</Alert> : null}
        <div className="flex items-start gap-3 rounded-[var(--radius-control)] border border-olive/40 bg-olive/10 px-4 py-3">
          <Icon name="check" className="mt-0.5 size-5 shrink-0 text-olive" />
          <div>
            <p className="font-medium text-olive">{t("highest")}</p>
            {me.my_top_bid ? (
              <p className="mt-1 text-sm text-text">{t("highestHint", { amount: formatUsd(me.my_top_bid) })}</p>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const submit = (value: string) => {
    setFeedback(null);
    const normalized = normalizeAmount(value);
    if (!normalized) return setLocalError(t("invalid"));
    if (Number(normalized) < Number(minimum)) return setLocalError(t("tooLowLocal", { amount: formatUsd(minimum) }));
    setLocalError(null);
    setConfirming(normalized);
  };

  const send = (value: string) => {
    if (attempt.current?.amount !== value) attempt.current = { amount: value, key: newKey() };
    bid.mutate({ id: detail.id, amount: value, key: attempt.current.key }, { onSettled: () => setConfirming(null) });
  };

  const outbid = Boolean(me?.alias && !me.is_highest && me.my_top_bid);
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;

  return (
    <div className="flex flex-col gap-4">
      {outbid && feedback?.tone !== "error" && feedback?.tone !== "unsure" ? (
        <Alert tone="error">
          <span className="font-medium">{t("outbid")}</span> — {t("outbidHint", { amount: formatUsd(me!.my_top_bid!) })}
        </Alert>
      ) : null}
      {feedback?.tone === "error" ? <Alert tone="error">{feedback.text}</Alert> : null}
      {feedback?.tone === "unsure" ? (
        <Alert tone="error">
          <p>{feedback.text}</p>
          <Button variant="secondary" className="mt-3" loading={bid.isPending} onClick={() => attempt.current && send(attempt.current.amount)}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit(amount);
        }}
        className="flex flex-col gap-3"
      >
        <label htmlFor={inputId} className="text-sm font-medium text-text">
          {t("amount")}
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id={inputId}
            inputMode="decimal"
            autoComplete="off"
            dir="ltr"
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              setLocalError(null);
            }}
            aria-invalid={localError ? true : undefined}
            aria-describedby={localError ? `${hintId} ${errorId}` : hintId}
            className={`min-h-12 flex-1 rounded-[var(--radius-control)] border bg-white px-4 text-lg font-medium tabular-nums text-text focus:border-secondary focus:outline-none ${
              localError ? "border-primary" : "border-border"
            }`}
          />
          <Button type="submit" className="min-h-12 shrink-0 sm:w-36" loading={bid.isPending} disabled={feedback?.tone === "unsure"}>
            {bid.isPending ? t("submitting") : t("submit")}
          </Button>
        </div>
        <p id={hintId} className="text-xs text-muted">
          {t("amountHint", { amount: formatUsd(minimum) })}
        </p>
        {localError ? (
          <p id={errorId} role="alert" className="text-sm text-primary">
            {localError}
          </p>
        ) : null}
        <fieldset className="flex flex-col gap-2">
          <legend className="text-xs text-muted">{t("quick")}</legend>
          <div className="flex flex-wrap gap-2">
            {quickAmounts(minimum, detail.minimum_increment).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  setAmount(value);
                  setLocalError(null);
                }}
                aria-pressed={normalizeAmount(amount) === value}
                className="min-h-10 rounded-full border border-border px-4 text-sm tabular-nums text-primary transition-colors duration-300 ease-calm hover:border-secondary aria-pressed:border-secondary aria-pressed:bg-secondary/10"
              >
                <bdi dir="ltr">{formatUsd(value)}</bdi>
              </button>
            ))}
          </div>
        </fieldset>
      </form>
      <p className="text-xs text-muted">{t("binding", { percent, window: paymentWindow })}</p>

      <ConfirmDialog
        open={confirming !== null}
        title={t("confirmTitle", { amount: formatUsd(confirming ?? minimum) })}
        confirmLabel={t("confirm")}
        cancelLabel={t("cancel")}
        busy={bid.isPending}
        onCancel={() => setConfirming(null)}
        onConfirm={() => confirming && send(confirming)}
      >
        {t("confirmBody", { percent, deposit: depositFor(confirming ?? minimum, detail.winner_deposit_percent), window: paymentWindow })}
      </ConfirmDialog>
    </div>
  );
}
