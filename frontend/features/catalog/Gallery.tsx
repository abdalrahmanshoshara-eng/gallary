"use client";

/* eslint-disable @next/next/no-img-element -- pre-generated WebP variants with srcset (see ResponsiveImage) */
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import type { PublicImage } from "@/lib/catalog/types";

export type GalleryImage = { id: string; alt: string; image: PublicImage };

function srcSet(image: PublicImage) {
  return image.variants.map((v) => `${v.url} ${v.width}w`).join(", ");
}

function largest(image: PublicImage) {
  return image.variants[image.variants.length - 1]?.url ?? "";
}

export function Gallery({ images }: { images: GalleryImage[] }) {
  const t = useTranslations("catalog.gallery");
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const count = images.length;
  const current = images[index];

  const go = useCallback((delta: number) => setIndex((i) => (i + delta + count) % count), [count]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  if (!current) return null;

  // In RTL the "next" image is to the left: ArrowLeft moves forward, ArrowRight moves back.
  const onKeyDown = (event: React.KeyboardEvent) => {
    const rtl = document.documentElement.dir === "rtl";
    if (event.key === "ArrowLeft") go(rtl ? 1 : -1);
    if (event.key === "ArrowRight") go(rtl ? -1 : 1);
  };

  return (
    <div>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("open")}
        className="flex aspect-[4/5] w-full cursor-zoom-in items-center justify-center rounded-[var(--radius-card)] bg-surface/60 p-6 md:aspect-square"
      >
        <img
          src={largest(current.image)}
          srcSet={srcSet(current.image)}
          sizes="(min-width: 1024px) 55vw, 95vw"
          width={current.image.width}
          height={current.image.height}
          alt={current.alt}
          fetchPriority={index === 0 ? "high" : undefined}
          className="h-full w-full object-contain"
        />
      </button>

      {count > 1 ? (
        <ul aria-label={t("thumbnails")} className="mt-4 flex flex-wrap gap-3">
          {images.map((img, i) => (
            <li key={img.id}>
              <button
                type="button"
                onClick={() => setIndex(i)}
                aria-current={i === index ? "true" : undefined}
                aria-label={t("imageOf", { current: i + 1, total: count })}
                className={[
                  "flex size-20 items-center justify-center rounded-[var(--radius-control)] bg-surface/60 p-1 transition",
                  i === index ? "ring-2 ring-secondary" : "opacity-70 hover:opacity-100",
                ].join(" ")}
              >
                <img
                  src={img.image.variants[0]?.url}
                  alt=""
                  loading="lazy"
                  width={img.image.width}
                  height={img.image.height}
                  className="h-full w-full object-contain"
                />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <dialog
        ref={dialogRef}
        onClose={() => {
          setOpen(false);
          triggerRef.current?.focus();
        }}
        onKeyDown={onKeyDown}
        aria-label={current.alt}
        className="m-0 h-dvh max-h-none w-dvw max-w-none bg-text/95 p-0 backdrop:bg-text/80"
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between p-4 text-sm text-white/80">
            <span>{t("imageOf", { current: index + 1, total: count })}</span>
            <button type="button" onClick={() => setOpen(false)} className="rounded px-3 py-2 text-white hover:bg-white/10">
              {t("close")}
            </button>
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center px-4 pb-6">
            <img
              src={largest(current.image)}
              srcSet={srcSet(current.image)}
              sizes="100vw"
              alt={current.alt}
              className="max-h-full max-w-full object-contain"
            />
            {count > 1 ? (
              <>
                <button
                  type="button"
                  onClick={() => go(-1)}
                  aria-label={t("previous")}
                  className="absolute start-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 px-4 py-3 text-2xl text-white hover:bg-white/20"
                >
                  <span aria-hidden className="inline-block rtl:-scale-x-100">‹</span>
                </button>
                <button
                  type="button"
                  onClick={() => go(1)}
                  aria-label={t("next")}
                  className="absolute end-4 top-1/2 -translate-y-1/2 rounded-full bg-white/10 px-4 py-3 text-2xl text-white hover:bg-white/20"
                >
                  <span aria-hidden className="inline-block rtl:-scale-x-100">›</span>
                </button>
              </>
            ) : null}
          </div>
        </div>
      </dialog>
    </div>
  );
}
