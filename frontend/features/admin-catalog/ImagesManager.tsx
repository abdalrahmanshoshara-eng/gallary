"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

import {
  artworkKey,
  deleteImage,
  reorderImages,
  updateImage,
  uploadArtworkImage,
  type AdminArtwork,
  type AdminArtworkImage,
} from "./api";
import { errorText } from "@/lib/forms";

/** Returns ids with the item at `index` moved by `delta` (bounded). */
export function moveId(ids: string[], index: number, delta: -1 | 1): string[] {
  const target = index + delta;
  if (target < 0 || target >= ids.length) return ids;
  const next = [...ids];
  [next[index], next[target]] = [next[target]!, next[index]!];
  return next;
}

function AltText({ image, onSave, busy }: { image: AdminArtworkImage; onSave: (v: string) => void; busy: boolean }) {
  const t = useTranslations("admin.artworks");
  const [value, setValue] = useState(image.alt_text ?? "");
  const dirty = value !== (image.alt_text ?? "");
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs">
        {t("altText")}
        <input
          className="min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3 text-sm"
          maxLength={250}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>
      {dirty ? (
        <Button variant="secondary" loading={busy} onClick={() => onSave(value)}>
          {t("saveAlt")}
        </Button>
      ) : null}
    </div>
  );
}

export function ImagesManager({ artwork }: { artwork: AdminArtwork }) {
  const t = useTranslations("admin.artworks");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const images = artwork.images;
  const key = artworkKey(artwork.id);
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });
  const onSaved = (saved: AdminArtwork) => {
    queryClient.setQueryData(key, saved);
    void queryClient.invalidateQueries({ queryKey: ["admin", "artworks"] });
  };

  // Sequential uploads: predictable order (first file = primary on an empty artwork) and no
  // burst of 20 parallel 15 MB requests through nginx.
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const errors: string[] = [];
      for (const file of files) {
        try {
          await uploadArtworkImage(artwork.id, file);
        } catch (error) {
          errors.push(t("uploadFailed", { name: file.name, error: errorText(error) }));
        }
      }
      setUploadErrors(errors);
    },
    onSettled: async () => {
      if (input.current) input.current.value = "";
      await refresh();
    },
  });
  const reorder = useMutation({ mutationFn: (ids: string[]) => reorderImages(artwork.id, ids), onSuccess: onSaved });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { alt_text?: string; is_primary?: boolean } }) =>
      updateImage(artwork.id, id, body),
    onSuccess: onSaved,
  });
  const remove = useMutation({ mutationFn: (id: string) => deleteImage(artwork.id, id), onSuccess: onSaved });
  const error = reorder.error ?? patch.error ?? remove.error;
  const busy = reorder.isPending || patch.isPending || remove.isPending;
  const ids = images.map((i) => i.id);

  return (
    <section aria-labelledby="artwork-images" className="flex flex-col gap-4">
      <h2 id="artwork-images" className="text-lg font-medium text-primary">
        {t("images")}
      </h2>
      <p className="text-xs text-muted">{t("imagesHint")}</p>
      {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
      {uploadErrors.map((message) => (
        <Alert key={message} tone="error">
          {message}
        </Alert>
      ))}
      {images.length === 0 ? <p className="text-sm text-muted">{t("noImages")}</p> : null}
      <ol className="flex flex-col gap-4">
        {images.map((image, index) => (
          <li
            key={image.id}
            className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-border/60 p-4 sm:flex-row"
          >
            <div className="flex size-32 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-control)] bg-surface text-center text-xs text-muted">
              {image.image.status === "ready" ? (
                <ResponsiveImage image={image.image} alt={image.alt_text ?? ""} sizes="8rem" />
              ) : image.image.status === "failed" ? (
                <span className="text-primary">{t("imageFailed")}</span>
              ) : (
                <span role="status">{t("imageProcessing")}</span>
              )}
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {image.is_primary ? (
                  <span className="rounded-full bg-primary px-3 py-1 text-xs text-on-primary">{t("primary")}</span>
                ) : (
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={() => patch.mutate({ id: image.id, body: { is_primary: true } })}
                  >
                    {t("makePrimary")}
                  </Button>
                )}
                <Button
                  variant="ghost"
                  disabled={busy || index === 0}
                  onClick={() => reorder.mutate(moveId(ids, index, -1))}
                >
                  {t("moveUp")}
                </Button>
                <Button
                  variant="ghost"
                  disabled={busy || index === images.length - 1}
                  onClick={() => reorder.mutate(moveId(ids, index, 1))}
                >
                  {t("moveDown")}
                </Button>
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm(t("confirmDeleteImage"))) remove.mutate(image.id);
                  }}
                >
                  {tc("delete")}
                </Button>
              </div>
              <AltText
                key={image.alt_text}
                image={image}
                busy={patch.isPending}
                onSave={(alt_text) => patch.mutate({ id: image.id, body: { alt_text } })}
              />
            </div>
          </li>
        ))}
      </ol>
      <div>
        <input
          ref={input}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          aria-label={t("addImages")}
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) upload.mutate(files);
          }}
        />
        <Button variant="secondary" loading={upload.isPending} onClick={() => input.current?.click()}>
          {upload.isPending ? t("uploading") : t("addImages")}
        </Button>
      </div>
    </section>
  );
}
