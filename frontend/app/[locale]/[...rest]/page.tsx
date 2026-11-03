import { notFound } from "next/navigation";

// Any unknown path inside a locale renders the localised not-found page.
export default function CatchAllPage() {
  notFound();
}
