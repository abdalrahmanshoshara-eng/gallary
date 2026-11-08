"use client";

import { useTranslations } from "next-intl";
import { useState, type KeyboardEvent } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Link } from "@/i18n/navigation";
import type { Schema } from "@/lib/api/types";

type Banner = Schema<"PublicBanner">;

function Cta({ banner }: { banner: Banner }) {
  if (!banner.link_url) return null;
  const cls =
    "mt-6 inline-flex min-h-12 items-center rounded-[var(--radius-control)] bg-background px-6 text-sm font-medium text-primary transition-colors duration-300 ease-calm hover:bg-white";
  return banner.link_url.startsWith("https://") ? (
    <a href={banner.link_url} className={cls} target="_blank" rel="noopener noreferrer">
      {banner.link_label}
    </a>
  ) : (
    <Link href={banner.link_url as "/"} className={cls}>
      {banner.link_label}
    </Link>
  );
}

/**
 * Home banners (F-CMS-03): one slide at a time, moved only by the visitor (buttons, dots or
 * arrow keys) — no autoplay, so nothing moves on its own and screen readers are not interrupted.
 */
export function HeroCarousel({ banners }: { banners: Banner[] }) {
  const t = useTranslations("home");
  const [index, setIndex] = useState(0);
  const count = banners.length;
  const go = (n: number) => setIndex((n + count) % count);
  const onKey = (e: KeyboardEvent) => {
    // RTL: the right arrow goes back, the left arrow goes forward.
    if (e.key === "ArrowLeft") go(index + 1);
    if (e.key === "ArrowRight") go(index - 1);
  };
  const banner = banners[index]!;

  return (
    <section aria-roledescription="carousel" aria-label={t("carousel")} onKeyDown={onKey} className="relative overflow-hidden bg-primary">
      <div
        role="group"
        aria-roledescription="slide"
        aria-label={t("slide", { n: index + 1, total: count })}
        className="relative min-h-[26rem] md:min-h-[32rem]"
      >
        <div className="absolute inset-0 [&_img]:h-full [&_img]:w-full [&_img]:object-cover">
          <ResponsiveImage image={banner.image} alt="" sizes="100vw" priority={index === 0} />
        </div>
        <div className="absolute inset-0 bg-gradient-to-t from-text/75 via-text/30 to-transparent" aria-hidden />
        <div className="relative mx-auto flex min-h-[26rem] max-w-[var(--container-max)] flex-col justify-end px-[var(--gutter)] pb-14 md:min-h-[32rem] md:pb-20">
          <h1 className="max-w-2xl text-3xl font-semibold text-on-primary md:text-5xl">{banner.title}</h1>
          {banner.subtitle ? <p className="mt-4 max-w-xl text-lg text-on-primary/90">{banner.subtitle}</p> : null}
          <Cta banner={banner} />
        </div>
      </div>
      {count > 1 ? (
        <div className="absolute inset-x-0 bottom-4 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => go(index - 1)}
            aria-label={t("previous")}
            className="inline-flex size-10 items-center justify-center rounded-full bg-background/80 text-primary hover:bg-background"
          >
            <span aria-hidden>›</span>
          </button>
          {banners.map((b, i) => (
            <button
              key={b.id}
              type="button"
              onClick={() => go(i)}
              aria-label={t("goTo", { n: i + 1 })}
              aria-current={i === index ? "true" : undefined}
              className={`size-2.5 rounded-full transition-colors duration-300 ease-calm ${i === index ? "bg-background" : "bg-background/45 hover:bg-background/70"}`}
            />
          ))}
          <button
            type="button"
            onClick={() => go(index + 1)}
            aria-label={t("next")}
            className="inline-flex size-10 items-center justify-center rounded-full bg-background/80 text-primary hover:bg-background"
          >
            <span aria-hidden>‹</span>
          </button>
        </div>
      ) : null}
      <span className="sr-only" aria-live="polite">
        {t("slide", { n: index + 1, total: count })}
      </span>
    </section>
  );
}
