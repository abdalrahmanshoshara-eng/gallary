"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

import { artistKey, getArtist, removeArtistPhoto, uploadArtistPhoto, type AdminArtist } from "./api";
import { errorText } from "./form-utils";

/** Upload / replace / remove an artist portrait. Polls while the worker renders variants. */
export function ArtistPhoto({ artist: initial }: { artist: AdminArtist }) {
  const t = useTranslations("admin.artists");
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const artist = useQuery({
    queryKey: artistKey(initial.id),
    queryFn: () => getArtist(initial.id),
    initialData: initial,
    refetchInterval: (q) => (q.state.data?.photo?.status === "pending" ? 2000 : false),
  });
  const photo = artist.data.photo;
  const onSaved = (saved: AdminArtist) => {
    queryClient.setQueryData(artistKey(saved.id), saved);
    void queryClient.invalidateQueries({ queryKey: ["admin", "artists"] });
  };
  const upload = useMutation({
    mutationFn: (file: File) => uploadArtistPhoto(initial.id, file),
    onSuccess: onSaved,
    onSettled: () => {
      if (input.current) input.current.value = "";
    },
  });
  const remove = useMutation({ mutationFn: () => removeArtistPhoto(initial.id), onSuccess: onSaved });
  const error = upload.error ?? remove.error;

  return (
    <section aria-labelledby="artist-photo" className="flex flex-col gap-4">
      <h2 id="artist-photo" className="text-lg font-medium text-primary">
        {t("photo")}
      </h2>
      {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
      {photo?.status === "ready" ? (
        <div className="aspect-square w-48 overflow-hidden rounded-[var(--radius-card)] bg-surface">
          <ResponsiveImage image={photo} alt={artist.data.name} sizes="12rem" />
        </div>
      ) : null}
      {photo?.status === "pending" ? (
        <p role="status" className="text-sm text-muted">
          {t("processing")}
        </p>
      ) : null}
      {photo?.status === "failed" ? <Alert tone="error">{t("processingFailed")}</Alert> : null}
      <p className="text-xs text-muted">{t("photoHint")}</p>
      <div className="flex flex-wrap gap-3">
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          id="artist-photo-input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
          }}
        />
        <Button variant="secondary" loading={upload.isPending} onClick={() => input.current?.click()}>
          {photo ? t("replacePhoto") : t("uploadPhoto")}
        </Button>
        {photo ? (
          <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>
            {t("removePhoto")}
          </Button>
        ) : null}
      </div>
    </section>
  );
}
