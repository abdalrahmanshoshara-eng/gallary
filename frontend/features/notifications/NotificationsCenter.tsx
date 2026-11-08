"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Link } from "@/i18n/navigation";

import {
  getUnreadCount,
  listKey,
  listNotifications,
  markAllRead,
  markRead,
  nextPage,
  notificationsKey,
  unreadCountKey,
  type AppNotification,
  type Page,
} from "./api";
import { EmailPreference } from "./EmailPreference";
import { dayHeading, notificationTime } from "./time";

type Filter = "all" | "unread";
type Href = Parameters<typeof Link>[0]["href"];

const CATEGORY_ICON: Record<string, IconName> = {
  order: "bag",
  auction: "gavel",
  request: "file",
  payout: "wallet",
};

/** Groups consecutive notifications by Damascus day, keeping the newest-first order. */
export function groupByDay(items: AppNotification[], now = new Date()) {
  const groups: { key: string; label: string; items: AppNotification[] }[] = [];
  for (const item of items) {
    const { key, label } = dayHeading(item.created_at, now);
    const last = groups.at(-1);
    if (last?.key === key) last.items.push(item);
    else groups.push({ key, label, items: [item] });
  }
  return groups;
}

function Row({
  item,
  onOpen,
}: {
  item: AppNotification;
  onOpen: (item: AppNotification) => void;
}) {
  const t = useTranslations("notifications");
  const content = (
    <>
      <span
        className={`mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full ${item.is_read ? "bg-surface text-muted" : "bg-primary/10 text-primary"}`}
        aria-hidden
      >
        <Icon
          name={CATEGORY_ICON[item.category] ?? "bell"}
          className="size-[18px]"
        />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span
          className={`text-sm ${item.is_read ? "text-text" : "font-semibold text-primary"}`}
        >
          {item.title}
        </span>
        {item.body ? (
          <span className="text-sm leading-6 whitespace-pre-line text-muted">
            {item.body}
          </span>
        ) : null}
        <span className="text-xs text-muted">
          {notificationTime(item.created_at)}
        </span>
      </span>
      {item.is_read ? null : (
        <span
          className="mt-2 size-2.5 shrink-0 rounded-full bg-secondary"
          role="img"
          aria-label={t("unreadDot")}
        />
      )}
    </>
  );
  const rowClass = `flex w-full items-start gap-3 px-3 py-4 text-start transition-colors duration-300 ease-calm hover:bg-surface/60 sm:px-4 ${
    item.is_read ? "" : "bg-white/70"
  }`;
  return (
    <li>
      {item.link ? (
        <Link
          href={item.link as Href}
          className={rowClass}
          onClick={() => onOpen(item)}
        >
          {content}
        </Link>
      ) : (
        <button type="button" className={rowClass} onClick={() => onOpen(item)}>
          {content}
        </button>
      )}
    </li>
  );
}

/**
 * The customer's notifications (§26): newest first, grouped by day, unread highlighted.
 * Opening one marks it read and goes to where it can be acted on.
 */
export function NotificationsCenter() {
  const t = useTranslations("notifications");
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const list = useInfiniteQuery({
    queryKey: listKey(filter),
    queryFn: ({ pageParam }) => listNotifications(filter, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => nextPage(last.next),
  });
  const unread = useQuery({
    queryKey: unreadCountKey,
    queryFn: getUnreadCount,
  });
  const unreadCount = unread.data?.unread ?? 0;

  const setRead = (id: string | "all") => {
    const now = new Date().toISOString();
    for (const f of ["all", "unread"] as const) {
      queryClient.setQueryData<InfiniteData<Page<AppNotification>>>(
        listKey(f),
        (data) =>
          data
            ? {
                ...data,
                pages: data.pages.map((page) => ({
                  ...page,
                  results: page.results.map((n) =>
                    id === "all" || n.id === id
                      ? { ...n, is_read: true, read_at: n.read_at ?? now }
                      : n,
                  ),
                })),
              }
            : data,
      );
    }
  };
  const readOne = useMutation({
    mutationFn: markRead,
    onMutate: (id) => {
      setRead(id);
      queryClient.setQueryData<{ unread: number }>(unreadCountKey, (d) =>
        d ? { unread: Math.max(0, d.unread - 1) } : d,
      );
    },
    onSettled: () =>
      void queryClient.invalidateQueries({ queryKey: unreadCountKey }),
  });
  const readAll = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      setRead("all");
      queryClient.setQueryData(unreadCountKey, { unread: 0 });
      void queryClient.invalidateQueries({ queryKey: notificationsKey });
    },
  });

  const open = (item: AppNotification) => {
    if (!item.is_read) readOne.mutate(item.id);
  };

  const items = list.data?.pages.flatMap((p) => p.results) ?? [];
  const groups = groupByDay(items);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label={t("filter")} className="flex gap-2">
          {(["all", "unread"] as const).map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-4 py-1.5 text-sm whitespace-nowrap transition-colors duration-300 ease-calm ${
                filter === f
                  ? "border-primary bg-primary text-on-primary"
                  : "border-border hover:border-secondary"
              }`}
            >
              {f === "unread" && unreadCount > 0
                ? t("unreadWithCount", { count: unreadCount })
                : t(f)}
            </button>
          ))}
        </div>
        {unreadCount > 0 ? (
          <Button
            variant="ghost"
            className="min-h-9 px-3"
            loading={readAll.isPending}
            onClick={() => readAll.mutate()}
          >
            {t("readAll")}
          </Button>
        ) : null}
      </div>

      {readAll.error ? <Alert tone="error">{t("actionError")}</Alert> : null}

      {list.isPending ? (
        <div className="flex flex-col gap-3" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-[var(--radius-card)] bg-surface/60"
            />
          ))}
        </div>
      ) : list.isError ? (
        <Alert tone="error">
          {t("loadError")}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => void list.refetch()}
          >
            {t("retry")}
          </button>
        </Alert>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-[var(--radius-card)] border border-border/60 px-6 py-12 text-center">
          <Icon
            name={filter === "unread" ? "check" : "bell"}
            className="size-8 text-secondary"
          />
          <p className="font-medium text-primary">
            {filter === "unread" ? t("allRead") : t("empty")}
          </p>
          <p className="max-w-md text-sm text-muted">
            {filter === "unread" ? t("allReadHint") : t("emptyHint")}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {groups.map((group) => (
            <section
              key={group.key}
              aria-labelledby={`day-${group.key}`}
              className="flex flex-col gap-2"
            >
              <h2
                id={`day-${group.key}`}
                className="text-xs font-medium text-muted"
              >
                {group.label === "today" || group.label === "yesterday"
                  ? t(group.label)
                  : group.label}
              </h2>
              <ul className="divide-y divide-border/50 overflow-hidden rounded-[var(--radius-card)] border border-border/60">
                {group.items.map((item) => (
                  <Row key={item.id} item={item} onOpen={open} />
                ))}
              </ul>
            </section>
          ))}
          {list.hasNextPage ? (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                loading={list.isFetchingNextPage}
                onClick={() => void list.fetchNextPage()}
              >
                {t("more")}
              </Button>
            </div>
          ) : null}
        </div>
      )}

      <EmailPreference />
    </div>
  );
}
