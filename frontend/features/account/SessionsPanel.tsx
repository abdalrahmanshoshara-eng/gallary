"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useRouter } from "@/i18n/navigation";
import { currentUserKey } from "@/lib/auth/useCurrentUser";
import { formatDateTime } from "@/lib/formatters/datetime";

import { endOtherSessions, endSession, listSessions, sessionsKey, type Session } from "./api";

function deviceLabel(userAgent: string, fallback: string): string {
  if (!userAgent) return fallback;
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /Chrome\//.test(userAgent)
      ? "Chrome"
      : /Firefox\//.test(userAgent)
        ? "Firefox"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : null;
  const os = /Android/.test(userAgent)
    ? "Android"
    : /iPhone|iPad/.test(userAgent)
      ? "iOS"
      : /Windows/.test(userAgent)
        ? "Windows"
        : /Mac OS X/.test(userAgent)
          ? "macOS"
          : /Linux/.test(userAgent)
            ? "Linux"
            : null;
  return [browser, os].filter(Boolean).join(" · ") || fallback;
}

export function SessionsPanel() {
  const t = useTranslations("account");
  const tc = useTranslations("common");
  const router = useRouter();
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: sessionsKey, queryFn: listSessions });

  const endOne = useMutation({
    mutationFn: (session: Session) => endSession(session.id),
    onSuccess: (_, session) => {
      if (session.current) {
        queryClient.setQueryData(currentUserKey, null);
        router.replace("/login");
        router.refresh();
        return;
      }
      void queryClient.invalidateQueries({ queryKey: sessionsKey });
    },
  });
  const endOthers = useMutation({
    mutationFn: endOtherSessions,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: sessionsKey }),
  });

  if (sessions.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (sessions.isError)
    return (
      <Alert tone="error">
        {tc("loadError")}{" "}
        <button type="button" className="underline" onClick={() => void sessions.refetch()}>
          {tc("retry")}
        </button>
      </Alert>
    );

  const others = sessions.data.filter((s) => !s.current).length;
  return (
    <div className="flex flex-col gap-6">
      {endOthers.isSuccess ? (
        <Alert tone="success">{t("othersLoggedOut", { count: endOthers.data.revoked })}</Alert>
      ) : null}
      <ul className="divide-y divide-border/60 border-y border-border/60">
        {sessions.data.map((session) => (
          <li key={session.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
            <div>
              <p className="font-medium">
                {deviceLabel(session.user_agent_summary, t("unknownDevice"))}
                {session.current ? <span className="ms-3 text-xs text-olive">{t("thisDevice")}</span> : null}
              </p>
              <p className="text-sm text-muted">{t("lastSeen", { time: formatDateTime(session.last_seen_at) })}</p>
            </div>
            {!session.current ? (
              <Button
                variant="ghost"
                loading={endOne.isPending && endOne.variables?.id === session.id}
                onClick={() => endOne.mutate(session)}
              >
                {t("endSession")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {others > 0 ? (
        <div>
          <Button variant="secondary" loading={endOthers.isPending} onClick={() => endOthers.mutate()}>
            {t("logoutOthers")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
