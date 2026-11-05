"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { Link, usePathname } from "@/i18n/navigation";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";
import { formatUsd } from "@/lib/formatters/money";
import { RealtimeSocket } from "@/lib/realtime/socket";

import { myBidsKey } from "./api";

type NoticeType = "auction.outbid" | "auction.won" | "auction.award_lost";
type Notice = { id: number; type: NoticeType; auction: string; title: string; amount?: string; order?: string };

const KNOWN: ReadonlySet<string> = new Set(["auction.outbid", "auction.won", "auction.award_lost"]);
const AUTO_DISMISS_MS = 12_000;

/**
 * The customer's private channel (`/ws/me/`): outbid / won / award-lost notices on any page.
 * Notices about the auction already on screen are skipped (that page shows them itself).
 */
export function LiveNotices() {
  const t = useTranslations("auctions.notices");
  const { data: user } = useCurrentUser();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const [notices, setNotices] = useState<Notice[]>([]);
  const customerId = user && !user.is_staff ? user.id : null;

  useEffect(() => {
    if (!customerId) return;
    const socket = new RealtimeSocket({ path: "/ws/me/" });
    let counter = 0;
    const off = socket.onMessage((message) => {
      if (!KNOWN.has(message.type)) return;
      const data = message.data as Record<string, string | undefined>;
      if (!data.auction) return;
      void queryClient.invalidateQueries({ queryKey: myBidsKey });
      if (message.type !== "auction.outbid") void queryClient.invalidateQueries({ queryKey: ["orders"] });
      if (window.location.pathname.endsWith(`/auctions/${data.auction}`)) return;
      counter += 1;
      const notice: Notice = {
        id: counter,
        type: message.type as NoticeType,
        auction: data.auction,
        title: data.title ?? "",
        amount: data.current_price ?? data.amount,
        order: data.order,
      };
      setNotices((current) => [...current.filter((n) => n.auction !== notice.auction), notice].slice(-3));
    });
    socket.start();
    return () => {
      off();
      socket.stop();
    };
  }, [customerId, queryClient]);

  // Outbid notices fade on their own; a win stays until the customer acts on it.
  useEffect(() => {
    const transient = notices.filter((n) => n.type !== "auction.won");
    if (transient.length === 0) return;
    const first = transient[0]!.id;
    const timer = setTimeout(() => setNotices((current) => current.filter((n) => n.id !== first)), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [notices]);

  if (!customerId) return null;
  // On the auction's own page its notice is redundant (that page shows the change itself).
  const visible = notices.filter((n) => !pathname.endsWith(`/auctions/${n.auction}`));
  const dismiss = (id: number) => setNotices((current) => current.filter((n) => n.id !== id));

  return (
    <section aria-label={t("region")} aria-live="assertive" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-3 px-4 sm:items-start sm:ps-6">
      {visible.map((notice) => {
        const key = notice.type.slice("auction.".length) as "outbid" | "won" | "award_lost";
        const href = notice.type === "auction.won" && notice.order ? `/orders/${notice.order}` : `/auctions/${notice.auction}`;
        return (
          <div
            key={notice.id}
            role="alert"
            className={`pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-[var(--radius-card)] border bg-white p-4 shadow-lg ${
              notice.type === "auction.won" ? "border-olive/50" : "border-secondary/60"
            }`}
          >
            <Icon name={notice.type === "auction.won" ? "check" : "clock"} className={`mt-0.5 size-5 shrink-0 ${notice.type === "auction.won" ? "text-olive" : "text-primary"}`} />
            <div className="min-w-0 flex-1 text-sm">
              <p className="text-text">{t(key, { title: notice.title, amount: notice.amount ? formatUsd(notice.amount) : "" })}</p>
              <Link href={href} onClick={() => dismiss(notice.id)} className="mt-2 inline-block font-medium text-primary underline-offset-4 hover:underline">
                {t("open")}
              </Link>
            </div>
            <button type="button" onClick={() => dismiss(notice.id)} aria-label={t("dismiss")} className="-m-2 inline-flex size-10 items-center justify-center rounded-full text-muted hover:bg-surface">
              <Icon name="close" className="size-4" />
            </button>
          </div>
        );
      })}
    </section>
  );
}
