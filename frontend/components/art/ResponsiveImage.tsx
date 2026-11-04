/* eslint-disable @next/next/no-img-element -- variants are pre-generated WebP files served
   from our media domain/CDN with a full srcset; next/image would re-encode them a second time. */
import type { PublicImage } from "@/lib/catalog/types";

type Props = {
  image: PublicImage;
  alt: string;
  /** CSS sizes attribute, e.g. "(min-width: 1024px) 33vw, 100vw". */
  sizes: string;
  className?: string;
  priority?: boolean;
};

/** Artwork-safe image: never cropped (object-contain), lazy by default, sharp on every screen. */
export function ResponsiveImage({ image, alt, sizes, className, priority = false }: Props) {
  const variants = image.variants;
  const fallback = variants.find((v) => v.width >= 1000) ?? variants[variants.length - 1];
  if (!fallback) return null;
  return (
    <img
      src={fallback.url}
      srcSet={variants.map((v) => `${v.url} ${v.width}w`).join(", ")}
      sizes={sizes}
      width={image.width}
      height={image.height}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : undefined}
      decoding="async"
      className={["h-full w-full object-contain", className].filter(Boolean).join(" ")}
    />
  );
}
