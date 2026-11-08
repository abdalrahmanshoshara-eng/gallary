"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AuctionCountdown } from "@/features/auctions/AuctionCountdown";
import { useAuctionLive } from "@/features/auctions/useAuctionLive";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/formatters/datetime";
import { formatUsd } from "@/lib/formatters/money";
import { errorText } from "@/lib/forms";

import { adminAuctionKey, cancelAuction, getAdminAuction, scheduleAuction, voidBid, type AdminAuction } from "./api";
import { AuctionForm } from "./AuctionForm";
import { AUCTION_TONE } from "./AuctionsTable";

const LIVE_STATUSES = new Set(["scheduled", "live", "pending_winner_payment"]);

type AdminBid = AdminAuction["bids"][number];

/** What voiding `target` does to the price, so the manager decides knowing the outcome. */
export function voidOutcome(bids: AdminBid[], target: AdminBid): { kind: "top"; next: AdminBid } | { kind: "opening" } | { kind: "lower" } {
  const ranked = bids
    .filter((b) => b.status !== "voided")
    .sort((x, y) => Number(y.amount) - Number(x.amount) || Date.parse(x.created_at) - Date.parse(y.created_at));
  if (ranked[0]?.id !== target.id) return { kind: "lower" };
  const next = ranked[1];
  return next ? { kind: "top", next } : { kind: "opening" };
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-4 border-b border-border/40 py-2 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** Subscribes to the auction's public stream and refreshes the staff view on every event. */
function LiveRefresh({ auction, onEvent }: { auction: AdminAuction; onEvent: () => void }) {
  const { lastEvent, serverNow } = useAuctionLive(auction.id);
  const t = useTranslations("auctions.countdown");
  useEffect(() => {
    if (lastEvent) onEvent();
  }, [lastEvent, onEvent]);
  if (auction.status !== "live" && auction.status !== "scheduled") return null;
  const upcoming = auction.status === "scheduled" && Date.parse(auction.starts_at) > serverNow();
  return (
    <p className="text-sm">
      <span className="text-muted">{upcoming ? t("startsIn") : t("endsIn")} </span>
      <AuctionCountdown deadline={upcoming ? auction.starts_at : auction.ends_at} serverNow={serverNow} className="font-semibold" />
    </p>
  );
}

export function AuctionManager({ id, justCreated }: { id: string; justCreated: boolean }) {
  const t = useTranslations("admin.auctions");
  const ts = useTranslations("status_auction");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [dialog, setDialog] = useState<"schedule" | "cancel" | null>(null);
  const [reason, setReason] = useState("");
  const [voiding, setVoiding] = useState<AdminBid | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const auction = useQuery({
    queryKey: adminAuctionKey(id),
    queryFn: () => getAdminAuction(id),
    // A copied photo is processed in the background: re-check until scheduling is possible.
    refetchInterval: (query) => (query.state.data?.schedule_problems.includes("primary_image_not_ready") ? 3000 : false),
  });
  const refresh = useCallback(() => void queryClient.invalidateQueries({ queryKey: adminAuctionKey(id) }), [queryClient, id]);

  const onDone = (message: string) => (result: AdminAuction) => {
    queryClient.setQueryData(adminAuctionKey(id), result);
    void queryClient.invalidateQueries({ queryKey: ["admin", "auctions"] });
    setDialog(null);
    setReason("");
    setNotice(message);
  };
  const schedule = useMutation({ mutationFn: () => scheduleAuction(id), onSuccess: onDone(t("scheduled")) });
  const cancel = useMutation({ mutationFn: () => cancelAuction(id, reason), onSuccess: onDone(t("cancelled")) });
  const voidMutation = useMutation({
    mutationFn: (target: AdminBid) => voidBid(id, target.id, voidReason),
    onSuccess: (result) => {
      onDone(t("voided"))(result);
      setVoiding(null);
      setVoidReason("");
    },
  });

  if (auction.isPending) return <div className="h-64 animate-pulse rounded-[var(--radius-card)] bg-surface/60" aria-busy />;
  if (auction.isError) {
    const missing = auction.error instanceof ApiError && auction.error.status === 404;
    return <Alert tone="error">{missing ? tc("loadError") : errorText(auction.error)}</Alert>;
  }
  const a = auction.data;
  const final = ["ended", "awarded", "cancelled"].includes(a.status);
  const scheduleError = schedule.error instanceof ApiError ? schedule.error : null;
  const problems = (scheduleError?.details as { problems?: string[] } | undefined)?.problems ?? a.schedule_problems;
  const winner = a.bids.find((b) => b.status === "winning");

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-primary md:text-3xl">{a.title}</h1>
          <p className="mt-1 text-sm text-muted">{a.creator_name}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={AUCTION_TONE[a.status] ?? "progress"}>{ts(a.status)}</StatusBadge>
          {a.status !== "draft" ? (
            <Link href={`/auctions/${a.id}`} className="text-sm text-primary underline-offset-4 hover:underline">
              {t("viewPublic")}
            </Link>
          ) : null}
        </div>
      </header>

      {justCreated && a.status === "draft" && !notice ? <Alert tone="success">{t("created")}</Alert> : null}
      {notice ? <Alert tone="success">{notice}</Alert> : null}
      {a.status === "cancelled" && a.cancelled_reason ? <Alert tone="info">{a.cancelled_reason}</Alert> : null}

      {!final && !editing ? (
        <section className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-5">
          {a.status === "draft" && problems.length ? (
            <Alert tone="error">
              <ul className="list-disc ps-5">
                {problems.map((p) => (
                  <li key={p}>{t(`problems.${p as "window_passed"}`)}</li>
                ))}
              </ul>
            </Alert>
          ) : null}
          {schedule.error && !problems.length ? <Alert tone="error">{errorText(schedule.error)}</Alert> : null}
          {cancel.error ? <Alert tone="error">{errorText(cancel.error)}</Alert> : null}
          <div className="flex flex-wrap gap-3">
            {a.status === "draft" ? (
              <Button onClick={() => setDialog("schedule")} disabled={problems.length > 0 && !scheduleError}>
                {t("schedule")}
              </Button>
            ) : null}
            {a.editable ? (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                {t("editTerms")}
              </Button>
            ) : null}
            {!final ? (
              <Button variant="ghost" onClick={() => setDialog("cancel")}>
                {t("cancel")}
              </Button>
            ) : null}
          </div>
          {!a.editable && !final && a.status !== "draft" ? <p className="text-xs text-muted">{t("frozen")}</p> : null}
        </section>
      ) : null}

      {editing ? (
        <section>
          <AuctionForm auction={a} onSaved={() => setEditing(false)} />
          <Button variant="ghost" className="mt-3" onClick={() => setEditing(false)}>
            {tc("cancel")}
          </Button>
        </section>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <section aria-labelledby="monitor" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 id="monitor" className="text-sm text-muted">
                  {t("monitor")}
                </h2>
                <bdi dir="ltr" className="text-3xl font-semibold text-primary tabular-nums">
                  {formatUsd(a.current_price ?? a.starting_price)}
                </bdi>
                <p className="text-xs text-muted">
                  {a.bid_count} · {t("extensions", { count: a.extensions_count, max: a.max_extensions })}
                </p>
              </div>
              {LIVE_STATUSES.has(a.status) ? <LiveRefresh auction={a} onEvent={refresh} /> : null}
            </div>

            {a.status === "pending_winner_payment" || a.status === "awarded" ? (
              <div className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-4 text-sm">
                <p>
                  <span className="text-muted">{t("winner")}: </span>
                  {winner ? `${winner.bidder} · ` : ""}
                  {winner ? <bdi dir="ltr">{winner.bidder_phone}</bdi> : null}
                </p>
                {a.payment_deadline && a.status === "pending_winner_payment" ? (
                  <p className="mt-1">
                    <span className="text-muted">{t("paymentDeadline")}: </span>
                    {formatDateTime(a.payment_deadline)}
                  </p>
                ) : null}
                {a.winner_order ? (
                  <p className="mt-2">
                    <Link href={`/admin/orders/${a.winner_order}`} className="font-medium text-primary underline-offset-4 hover:underline">
                      {t("winnerOrder")} <span dir="ltr">{a.winner_order}</span>
                    </Link>
                  </p>
                ) : null}
              </div>
            ) : null}
            {a.outcome ? <p className="text-sm text-muted">{t(`outcome.${a.outcome as "sold"}`)}</p> : null}

            <h3 className="mt-2 text-base font-medium text-primary">{t("bids")}</h3>
            {a.bids.length > 0 && a.status !== "draft" && a.status !== "cancelled" ? (
              <p className="text-xs text-muted">{a.bids_voidable ? t("voidNote") : t("voidHint")}</p>
            ) : null}
            {a.bids.length === 0 ? (
              <p className="text-sm text-muted">{t("noBids")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[36rem] text-sm">
                  <thead className="text-start text-xs text-muted">
                    <tr>
                      <th className="px-2 py-2 text-start font-normal">{t("bidder")}</th>
                      <th className="px-2 py-2 text-start font-normal">{t("phone")}</th>
                      <th className="px-2 py-2 text-start font-normal">{tc("status")}</th>
                      <th className="px-2 py-2 text-start font-normal">{t("time")}</th>
                      <th className="px-2 py-2 text-end font-normal">USD</th>
                      {a.bids_voidable ? (
                        <th className="px-2 py-2 text-end font-normal">
                          <span className="sr-only">{tc("actions")}</span>
                        </th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {a.bids.map((bid) => {
                      const voided = bid.status === "voided";
                      return (
                        <tr key={bid.id} className={voided ? "text-muted" : undefined}>
                          <td className="px-2 py-2">
                            {bid.bidder} <span className="text-xs text-muted">#{bid.alias}</span>
                          </td>
                          <td className="px-2 py-2">
                            <bdi dir="ltr">{bid.bidder_phone}</bdi>
                          </td>
                          <td className="px-2 py-2">
                            {t(`bidStatus.${bid.status as "valid"}`)}
                            {voided && bid.void_reason ? <span className="block max-w-56 text-xs">{bid.void_reason}</span> : null}
                          </td>
                          <td className="px-2 py-2 text-xs text-muted">{formatDateTime(bid.created_at)}</td>
                          <td className={`py-2 text-end tabular-nums ${voided ? "line-through" : ""}`}>
                            <bdi dir="ltr">{formatUsd(bid.amount)}</bdi>
                          </td>
                          {a.bids_voidable ? (
                            <td className="px-2 py-2 text-end">
                              {!voided ? (
                                <button
                                  type="button"
                                  onClick={() => {
                                    voidMutation.reset();
                                    setVoiding(bid);
                                  }}
                                  aria-label={t("voidBidLabel", { bidder: bid.bidder, amount: formatUsd(bid.amount) })}
                                  className="min-h-9 rounded-[var(--radius-control)] px-3 text-xs text-primary underline-offset-4 hover:bg-surface hover:underline"
                                >
                                  {t("voidBid")}
                                </button>
                              ) : null}
                            </td>
                          ) : null}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <aside className="flex flex-col gap-6">
            <section aria-labelledby="settings">
              <h2 id="settings" className="mb-2 text-lg font-medium text-primary">
                {t("details")}
              </h2>
              <dl>
                <Row label={t("fields.starts_at")}>{formatDateTime(a.starts_at)}</Row>
                <Row label={t("fields.ends_at")}>{formatDateTime(a.ends_at)}</Row>
                <Row label={t("fields.starting_price")}>
                  <bdi dir="ltr">{formatUsd(a.starting_price)}</bdi>
                </Row>
                <Row label={t("fields.minimum_increment")}>
                  <bdi dir="ltr">{formatUsd(a.minimum_increment)}</bdi>
                </Row>
                <Row label={t("reserve")}>{a.reserve_price ? <bdi dir="ltr">{formatUsd(a.reserve_price)}</bdi> : t("noReserve")}</Row>
                <Row label={t("fields.winner_deposit_percent")}>{Number(a.winner_deposit_percent)}%</Row>
                <Row label={t("commission")}>{a.commission_rate ? `${Number(a.commission_rate)}%` : t("defaultCommission")}</Row>
                <Row label={t("fields.non_payment_policy")}>{t(`policy.${a.non_payment_policy}`)}</Row>
              </dl>
            </section>
            <section aria-labelledby="history">
              <h2 id="history" className="mb-2 text-lg font-medium text-primary">
                {t("history")}
              </h2>
              <ol className="flex flex-col gap-2 text-sm">
                {(a.history as { to_status: string; reason: string; actor: string | null; at: string }[]).map((h, index) => (
                  <li key={index} className="border-s-2 border-border ps-3">
                    <span className="font-medium">{ts(h.to_status as "draft")}</span>
                    <span className="block text-xs text-muted">
                      {formatDateTime(h.at)}
                      {h.actor ? ` · ${h.actor}` : ""}
                    </span>
                    {h.reason ? <span className="block text-xs">{h.reason}</span> : null}
                  </li>
                ))}
              </ol>
            </section>
          </aside>
        </div>
      )}

      <ConfirmDialog
        open={dialog === "schedule"}
        title={t("scheduleTitle")}
        confirmLabel={t("schedule")}
        cancelLabel={tc("cancel")}
        busy={schedule.isPending}
        onCancel={() => setDialog(null)}
        onConfirm={() => schedule.mutate(undefined, { onError: () => setDialog(null) })}
      >
        {t("scheduleBody")}
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === "cancel"}
        title={t("cancelTitle")}
        confirmLabel={t("cancel")}
        cancelLabel={tc("back")}
        busy={cancel.isPending}
        confirmDisabled={!reason.trim()}
        onCancel={() => setDialog(null)}
        onConfirm={() => cancel.mutate(undefined, { onError: () => setDialog(null) })}
      >
        <p>{t("cancelBody")}</p>
        <label className="mt-4 flex flex-col gap-1 text-sm text-text">
          {t("cancelReason")}
          <textarea
            className="min-h-20 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          />
        </label>
      </ConfirmDialog>
      <ConfirmDialog
        open={voiding !== null}
        title={voiding ? t("voidTitle", { bidder: voiding.bidder, amount: formatUsd(voiding.amount) }) : ""}
        confirmLabel={t("voidConfirm")}
        cancelLabel={tc("back")}
        busy={voidMutation.isPending}
        confirmDisabled={!voidReason.trim()}
        onCancel={() => {
          setVoiding(null);
          setVoidReason("");
        }}
        onConfirm={() => voiding && voidMutation.mutate(voiding)}
      >
        {voiding
          ? (() => {
              const outcome = voidOutcome(a.bids, voiding);
              return (
                <p className="font-medium text-text">
                  {outcome.kind === "top"
                    ? t("voidTop", { bidder: outcome.next.bidder, amount: formatUsd(outcome.next.amount) })
                    : outcome.kind === "opening"
                      ? t("voidTopOpening", { amount: formatUsd(a.starting_price) })
                      : t("voidLower")}
                </p>
              );
            })()
          : null}
        <p className="mt-2">{t("voidNote")}</p>
        {voidMutation.error ? (
          <div className="mt-3">
            <Alert tone="error">{errorText(voidMutation.error)}</Alert>
          </div>
        ) : null}
        <label className="mt-4 flex flex-col gap-1 text-sm text-text">
          {t("voidReason")}
          <textarea
            className="min-h-20 rounded-[var(--radius-control)] border border-border bg-white px-3 py-2"
            value={voidReason}
            onChange={(e) => setVoidReason(e.target.value)}
            required
          />
        </label>
      </ConfirmDialog>
    </div>
  );
}
