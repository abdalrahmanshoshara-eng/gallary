import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { subscribeMe } from "@/lib/realtime/me";
import type { RealtimeSocket } from "@/lib/realtime/socket";
import messages from "@/messages/ar.json";

import { nextPage, type AppNotification } from "./api";
import { groupByDay, NotificationsCenter } from "./NotificationsCenter";
import { notificationTime } from "./time";

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={String(href)} {...rest}>
      {children}
    </a>
  ),
}));

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const NOW = new Date("2026-11-08T12:00:00Z"); // 15:00 in Damascus
const note = (
  id: string,
  created_at: string,
  over: Partial<AppNotification> = {},
): AppNotification => ({
  id,
  kind: "order.created",
  category: "order" as const,
  title: `إشعار ${id}`,
  body: "نص",
  link: `/orders/ART-${id}`,
  created_at,
  read_at: null,
  is_read: false,
  ...over,
});

describe("time and grouping", () => {
  it("says how long ago, then the full date", () => {
    expect(notificationTime("2026-11-08T11:59:30Z", NOW)).toBe("الآن");
    expect(notificationTime("2026-11-08T11:55:00Z", NOW)).toBe("قبل 5 دقائق");
    expect(notificationTime("2026-11-08T09:00:00Z", NOW)).toBe("قبل 3 ساعات");
    expect(notificationTime("2026-11-01T09:00:00Z", NOW)).toContain(
      "تشرين الثاني",
    );
  });

  it("groups by Damascus day", () => {
    const groups = groupByDay(
      [
        note("1", "2026-11-08T11:00:00Z"),
        note("2", "2026-11-07T22:30:00Z"),
        note("3", "2026-11-07T20:00:00Z"),
        note("4", "2026-11-05T10:00:00Z"),
      ],
      NOW,
    );
    // 22:30 UTC on the 7th is 01:30 on the 8th in Damascus → today.
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([
      ["today", ["1", "2"]],
      ["yesterday", ["3"]],
      [expect.stringContaining("5 تشرين الثاني"), ["4"]],
    ]);
  });

  it("reads the next page from DRF links", () => {
    expect(nextPage("http://h/api/v1/notifications?page=3&page_size=20")).toBe(
      3,
    );
    expect(nextPage(null)).toBeUndefined();
  });
});

describe("subscribeMe", () => {
  it("shares one socket and closes it with the last listener", () => {
    const created: {
      started: number;
      stopped: number;
      emit: (m: unknown) => void;
    }[] = [];
    const factory = () => {
      const listeners: ((m: unknown) => void)[] = [];
      const fake = {
        started: 0,
        stopped: 0,
        emit: (m: unknown) => listeners.forEach((l) => l(m)),
      };
      created.push(fake);
      return {
        onMessage: (l: (m: unknown) => void) => listeners.push(l),
        onOpen: () => () => undefined,
        start: () => void fake.started++,
        stop: () => void fake.stopped++,
      } as unknown as RealtimeSocket;
    };
    const a = vi.fn();
    const b = vi.fn();
    const offA = subscribeMe({ onMessage: a }, factory);
    const offB = subscribeMe({ onMessage: b }, factory);
    expect(created).toHaveLength(1);
    created[0]!.emit({ type: "notification.created" });
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    offA();
    expect(created[0]!.stopped).toBe(0);
    offB();
    expect(created[0]!.stopped).toBe(1);
  });
});

describe("NotificationsCenter", () => {
  let routes: Record<string, (init?: RequestInit, url?: URL) => Response>;
  let fetchMock: ReturnType<typeof vi.fn>;

  function renderUi() {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    return render(
      <NextIntlClientProvider
        locale="ar"
        messages={messages}
        timeZone="Asia/Damascus"
      >
        <QueryClientProvider client={client}>
          <NotificationsCenter />
        </QueryClientProvider>
      </NextIntlClientProvider>,
    );
  }

  beforeEach(() => {
    vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
    fetchMock = vi.fn((url: string, init?: RequestInit) => {
      const parsed = new URL(url, "http://x");
      const key = `${init?.method ?? "GET"} ${parsed.pathname.replace(/^\/api\/v1/, "")}`;
      return Promise.resolve(
        routes[key]
          ? routes[key]!(init, parsed)
          : json(404, { error: { code: "NOT_FOUND", message: key } }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    routes = {
      "GET /notifications/preferences": () =>
        json(200, {
          email_enabled: true,
          email_available: true,
          has_email: false,
        }),
    };
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists, marks one read on open, and marks all read", async () => {
    const now = new Date().toISOString();
    const read = new Set(["c"]);
    const rows = () =>
      ["a", "b", "c"].map((id) =>
        note(id, now, read.has(id) ? { is_read: true, read_at: now } : {}),
      );
    routes["GET /notifications/unread-count"] = () =>
      json(200, { unread: 3 - read.size });
    routes["GET /notifications"] = () =>
      json(200, { count: 3, next: null, previous: null, results: rows() });
    routes["POST /notifications/a/read"] = () => {
      read.add("a");
      return json(200, note("a", now, { is_read: true, read_at: now }));
    };
    routes["POST /notifications/read-all"] = () => {
      ["a", "b"].forEach((id) => read.add(id));
      return json(200, { updated: 1, unread: 0 });
    };
    renderUi();

    const first = await screen.findByRole("link", { name: /إشعار a/ });
    expect(first).toHaveAttribute("href", "/orders/ART-a");
    expect(screen.getAllByRole("img", { name: "غير مقروء" })).toHaveLength(2);
    expect(
      await screen.findByRole("tab", { name: "غير المقروءة (2)" }),
    ).toBeInTheDocument();

    fireEvent.click(first);
    await waitFor(() =>
      expect(screen.getAllByRole("img", { name: "غير مقروء" })).toHaveLength(1),
    );
    expect(
      fetchMock.mock.calls.some(
        ([u, i]) =>
          String(u).endsWith("/notifications/a/read") && i?.method === "POST",
      ),
    ).toBe(true);

    fireEvent.click(
      await screen.findByRole("button", { name: "تعليم الكل كمقروء" }),
    );
    await waitFor(() =>
      expect(screen.queryAllByRole("img", { name: "غير مقروء" })).toHaveLength(
        0,
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "تعليم الكل كمقروء" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("explains the empty states and why e-mail is off", async () => {
    routes["GET /notifications/unread-count"] = () => json(200, { unread: 0 });
    routes["GET /notifications"] = () =>
      json(200, { count: 0, next: null, previous: null, results: [] });
    renderUi();
    expect(await screen.findByText("لا إشعارات بعد")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "تعليم الكل كمقروء" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "غير المقروءة" }));
    expect(await screen.findByText("قرأت كل شيء")).toBeInTheDocument();

    const toggle = await screen.findByRole("switch", {
      name: "نسخة بالبريد الإلكتروني",
    });
    expect(toggle).toBeDisabled();
    expect(
      screen.getByRole("link", { name: "أضف بريدك في صفحة الحساب" }),
    ).toHaveAttribute("href", "/account");
  });

  it("hides the e-mail section when the platform does not send e-mail, and loads more", async () => {
    const now = new Date().toISOString();
    routes["GET /notifications/preferences"] = () =>
      json(200, {
        email_enabled: true,
        email_available: false,
        has_email: true,
      });
    routes["GET /notifications/unread-count"] = () => json(200, { unread: 0 });
    routes["GET /notifications"] = (_i, url) =>
      url?.searchParams.get("page") === "2"
        ? json(200, {
            count: 2,
            next: null,
            previous: "p1",
            results: [note("old", now, { is_read: true })],
          })
        : json(200, {
            count: 2,
            next: "http://h/api/v1/notifications?page=2",
            previous: null,
            results: [note("new", now, { is_read: true })],
          });
    renderUi();
    fireEvent.click(await screen.findByRole("button", { name: "عرض المزيد" }));
    expect(await screen.findByText("إشعار old")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "عرض المزيد" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
  });

  it("offers a retry when loading fails", async () => {
    routes["GET /notifications/unread-count"] = () => json(200, { unread: 0 });
    routes["GET /notifications"] = () =>
      json(500, { error: { code: "SERVER_ERROR", message: "x" } });
    renderUi();
    expect(
      await screen.findByText(/تعذّر تحميل الإشعارات/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "إعادة المحاولة" }),
    ).toBeInTheDocument();
  });
});
