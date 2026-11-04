"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api/errors";
import type { RoleName } from "@/lib/auth/types";
import { formatDateTime } from "@/lib/formatters/datetime";

import { listUsers, revokeUserSessions, setActive, usersKey, type AdminUser } from "./api";
import { SetPasswordControl } from "./SetPasswordControl";

const PAGE_SIZE = 25;
const selectClass = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function UserRow({ user, currentUserId, onChanged }: { user: AdminUser; currentUserId: string; onChanged: () => void }) {
  const t = useTranslations("admin.users");
  const tr = useTranslations("admin.roles");
  const tc = useTranslations("common");
  const [askReason, setAskReason] = useState(false);
  const [reason, setReason] = useState("");
  const toggle = useMutation({
    mutationFn: () => setActive(user.id, !user.is_active, reason),
    onSuccess: () => {
      setAskReason(false);
      setReason("");
      onChanged();
    },
  });
  const sessions = useMutation({ mutationFn: () => revokeUserSessions(user.id) });
  const isSelf = user.id === currentUserId;
  const error = toggle.error ?? sessions.error;

  return (
    <tr className="align-top">
      <td className="py-4 pe-4">
        <p className="font-medium">{user.display_name || "—"}</p>
        <bdi dir="ltr" className="text-sm text-muted">
          {user.phone}
        </bdi>
        {user.roles.length ? (
          <p className="text-xs text-secondary">{user.roles.map((r) => tr(r as RoleName)).join("، ")}</p>
        ) : null}
      </td>
      <td className="py-4 pe-4 text-sm">{user.is_active ? t("active") : <span className="text-primary">{t("inactive")}</span>}</td>
      <td className="py-4 pe-4 text-sm text-muted">{formatDateTime(user.date_joined)}</td>
      <td className="py-4">
        {isSelf ? null : (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-2">
              {user.is_active ? (
                <Button variant="ghost" onClick={() => setAskReason((v) => !v)}>
                  {askReason ? tc("cancel") : t("deactivate")}
                </Button>
              ) : (
                <Button variant="ghost" loading={toggle.isPending} onClick={() => toggle.mutate()}>
                  {t("activate")}
                </Button>
              )}
              <Button variant="ghost" loading={sessions.isPending} onClick={() => sessions.mutate()}>
                {t("revokeSessions")}
              </Button>
            </div>
            <SetPasswordControl userId={user.id} />
            {askReason ? (
              <div className="flex flex-wrap items-end gap-2">
                <label className="flex flex-col gap-1 text-xs">
                  {t("deactivateReason")}
                  <input className={selectClass} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
                </label>
                <Button loading={toggle.isPending} onClick={() => toggle.mutate()}>
                  {t("deactivate")}
                </Button>
              </div>
            ) : null}
            {sessions.isSuccess ? <p className="text-xs text-olive">{t("sessionsRevoked", { count: sessions.data.revoked })}</p> : null}
            {error instanceof ApiError ? <p className="text-xs text-primary">{error.message}</p> : null}
          </div>
        )}
      </td>
    </tr>
  );
}

export function UsersTable({ currentUserId }: { currentUserId: string }) {
  const t = useTranslations("admin.users");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const params = { search: debouncedSearch, kind, is_active: status, page: String(page) };
  const users = useQuery({ queryKey: usersKey(params), queryFn: () => listUsers(params), placeholderData: keepPreviousData });
  const totalPages = users.data ? Math.max(1, Math.ceil(users.data.count / PAGE_SIZE)) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-4">
        <label className="flex min-w-64 flex-1 flex-col gap-1 text-sm">
          {t("search")}
          <input type="search" className={selectClass} value={search} onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("kind")}
          <select className={selectClass} value={kind} onChange={(e) => {
              setKind(e.target.value);
              setPage(1);
            }}>
            <option value="">{t("kindAll")}</option>
            <option value="customer">{t("kindCustomer")}</option>
            <option value="staff">{t("kindStaff")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("status")}
          <select className={selectClass} value={status} onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}>
            <option value="">{t("statusAll")}</option>
            <option value="true">{t("active")}</option>
            <option value="false">{t("inactive")}</option>
          </select>
        </label>
      </div>

      {users.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {users.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {users.data ? (
        users.data.results.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-start">
              <thead className="border-b border-border/60 text-sm text-muted">
                <tr>
                  <th className="py-3 pe-4 text-start font-normal">{t("title")}</th>
                  <th className="py-3 pe-4 text-start font-normal">{t("status")}</th>
                  <th className="py-3 pe-4 text-start font-normal">{t("joined")}</th>
                  <th className="py-3 text-start font-normal">{t("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {users.data.results.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    currentUserId={currentUserId}
                    onChanged={() => void queryClient.invalidateQueries({ queryKey: ["admin", "users"] })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted">{t("empty")}</p>
        )
      ) : null}

      {users.data && totalPages > 1 ? (
        <nav className="flex items-center gap-4 text-sm" aria-label={t("title")}>
          <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {tc("previous")}
          </Button>
          <span>{tc("pageOf", { page, total: totalPages })}</span>
          <Button variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            {tc("next")}
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
