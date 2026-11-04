"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";

import { artworkKey, getArtwork, type AdminArtwork } from "./api";
import { ArtworkForm } from "./ArtworkForm";
import { ArtworkStatusPanel } from "./ArtworkStatusPanel";
import { ImagesManager } from "./ImagesManager";

/** One cached artwork shared by every panel; polls while any image is still being processed. */
export function ArtworkEditor({ initial, justCreated }: { initial: AdminArtwork; justCreated: boolean }) {
  const t = useTranslations("admin.artworks");
  const artwork = useQuery({
    queryKey: artworkKey(initial.id),
    queryFn: () => getArtwork(initial.id),
    initialData: initial,
    refetchInterval: (q) => (q.state.data?.images.some((i) => i.image.status === "pending") ? 2000 : false),
  });
  const data = artwork.data;
  return (
    <div className="flex flex-col gap-12">
      {justCreated && data.images.length === 0 ? <Alert tone="success">{t("createdDraft")}</Alert> : null}
      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <ImagesManager artwork={data} />
        <ArtworkStatusPanel artwork={data} />
      </div>
      <ArtworkForm artwork={initial} />
    </div>
  );
}
