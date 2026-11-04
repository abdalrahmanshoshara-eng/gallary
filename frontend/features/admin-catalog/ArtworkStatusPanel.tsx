"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Link, useRouter } from "@/i18n/navigation";

import { artworkAction, artworkKey, deleteArtwork, type AdminArtwork } from "./api";
import { errorText } from "@/lib/forms";

type Problem = "primary_image_missing" | "primary_image_not_ready" | "category_inactive" | "artist_hidden" | "creator_missing" | "title_missing";
type Status = "draft" | "published" | "hidden";

export function ArtworkStatusPanel({ artwork }: { artwork: AdminArtwork }) {
  const t = useTranslations("admin.artworks");
  const format = useFormatter();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [visibility, setVisibility] = useState<"visible" | "hidden">("visible");
  const [reason, setReason] = useState("");
  const status = (artwork.publication_status ?? "draft") as Status;
  const problems = (artwork.publish_problems ?? []) as Problem[];

  const action = useMutation({
    mutationFn: ({ name, body }: { name: Parameters<typeof artworkAction>[1]; body?: Record<string, unknown> }) =>
      artworkAction(artwork.id, name, body),
    onSuccess: (saved) => {
      queryClient.setQueryData(artworkKey(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: ["admin", "artworks"] });
      setReason("");
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteArtwork(artwork.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "artworks"] });
      router.replace("/admin/artworks");
    },
  });
  const busy = action.isPending || remove.isPending;
  const date = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" });
  const isPublic =
    status === "published" && (!artwork.is_archived || artwork.archive_visibility === "visible");

  return (
    <section
      aria-labelledby="artwork-publication"
      className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-border/60 p-6"
    >
      <h2 id="artwork-publication" className="text-lg font-medium text-primary">
        {t("publication")}
      </h2>
      <dl className="grid gap-1 text-sm">
        <div className="flex gap-2">
          <dt className="text-muted">{t("statusLabel")}:</dt>
          <dd className="font-medium">{t(`status.${status}`)}</dd>
        </div>
        {artwork.published_at ? <dd className="text-muted">{t("publishedAt", { date: date(artwork.published_at) })}</dd> : null}
        {artwork.is_archived && artwork.archived_at ? (
          <dd className="text-muted">
            {t("archivedAt", { date: date(artwork.archived_at) })} ·{" "}
            {artwork.archive_visibility === "hidden" ? t("archivedHiddenNote") : t("archivedVisibleNote")}
          </dd>
        ) : null}
      </dl>

      {action.error ?? remove.error ? <Alert tone="error">{errorText(action.error ?? remove.error)}</Alert> : null}

      {status !== "published" && !artwork.is_archived ? (
        problems.length ? (
          <div className="text-sm">
            <p className="font-medium">{t("requirements")}</p>
            <ul className="mt-1 list-inside list-disc text-primary">
              {problems.map((p) => (
                <li key={p}>{t(`problems.${p}`)}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-olive">{t("readyToPublish")}</p>
        )
      ) : null}

      <div className="flex flex-wrap gap-3">
        {status !== "published" ? (
          <Button
            disabled={problems.length > 0}
            loading={busy && action.variables?.name === "publish"}
            onClick={() => action.mutate({ name: "publish" })}
          >
            {status === "hidden" ? t("republish") : t("publish")}
          </Button>
        ) : null}
        {status === "published" && !artwork.is_archived ? (
          <Button variant="secondary" disabled={busy} onClick={() => action.mutate({ name: "hide", body: { reason } })}>
            {t("hide")}
          </Button>
        ) : null}
        {artwork.is_archived ? (
          <Button variant="secondary" disabled={busy} onClick={() => action.mutate({ name: "unarchive" })}>
            {t("unarchive")}
          </Button>
        ) : null}
        {status === "draft" && !artwork.published_at ? (
          <Button
            variant="ghost"
            loading={remove.isPending}
            disabled={busy}
            onClick={() => {
              if (window.confirm(t("confirmDeleteDraft"))) remove.mutate();
            }}
          >
            {t("deleteDraft")}
          </Button>
        ) : null}
        {isPublic ? (
          <Link
            href={`/artworks/${artwork.slug}`}
            className="inline-flex min-h-11 items-center px-2 text-sm text-primary underline hover:text-secondary"
          >
            {t("viewPublic")}
          </Link>
        ) : null}
      </div>

      {status === "published" && !artwork.is_archived ? (
        <div className="flex flex-col gap-3 border-t border-border/60 pt-4">
          <p className="text-sm font-medium">{t("archive")}</p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm">
              {t("archiveVisibility")}
              <select
                className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as "visible" | "hidden")}
              >
                <option value="visible">{t("visibilityVisible")}</option>
                <option value="hidden">{t("visibilityHidden")}</option>
              </select>
            </label>
            <label className="flex min-w-48 flex-1 flex-col gap-1 text-sm">
              {t("reason")}
              <input
                className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => action.mutate({ name: "archive", body: { visibility, reason } })}
            >
              {t("archive")}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
