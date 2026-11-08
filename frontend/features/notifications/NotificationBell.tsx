"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { Icon } from "@/components/ui/Icon";
import { Link } from "@/i18n/navigation";
import { subscribeMe } from "@/lib/realtime/me";

import { getUnreadCount, notificationsKey, unreadCountKey } from "./api";

/** Header bell for customers: unread count, updated live from `/ws/me/` and on tab focus. */
export function NotificationBell({ className }: { className: string }) {
  const t = useTranslations("notifications");
  const queryClient = useQueryClient();
  const unread = useQuery({
    queryKey: unreadCountKey,
    queryFn: getUnreadCount,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const count = unread.data?.unread ?? 0;

  useEffect(
    () =>
      subscribeMe({
        onMessage: (message) => {
          if (message.type === "notification.created")
            void queryClient.invalidateQueries({ queryKey: notificationsKey });
        },
        onOpen: ({ reconnected }) => {
          if (reconnected)
            void queryClient.invalidateQueries({ queryKey: notificationsKey });
        },
      }),
    [queryClient],
  );

  return (
    <Link
      href="/notifications"
      className={className}
      aria-label={t("bell", { count })}
    >
      <Icon name="bell" className="size-6" />
      {count > 0 ? (
        <span
          aria-hidden
          className="absolute -end-0.5 top-0.5 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] leading-5 text-on-primary tabular-nums"
        >
          {count > 9 ? "9+" : count}
        </span>
      ) : null}
    </Link>
  );
}
