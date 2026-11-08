/** Inline line icons (no icon font, no network). Decorative by default: label the control, not the icon. */
const PATHS = {
  bag: "M6 8h12l-1 12H7L6 8zm3 0V6a3 3 0 0 1 6 0v2",
  heart: "M12 20.5s-7.5-4.6-9.3-9.2C1.4 8 3.4 4.5 7 4.5c2 0 3.4 1.1 5 3 1.6-1.9 3-3 5-3 3.6 0 5.6 3.5 4.3 6.8-1.8 4.6-9.3 9.2-9.3 9.2z",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6L6 18",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8a7 7 0 0 1 14 0",
  minus: "M6 12h12",
  plus: "M12 6v12M6 12h12",
  check: "M5 12.5l4.5 4.5L19 7",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  trash: "M5 7h14M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  bell: "M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15l1.5-2zM10 21a2 2 0 0 0 4 0",
  gavel: "M13.5 4.5l6 6M11 7l6 6M10 8l6 6-2.5 2.5-6-6L10 8zM4 20l6.5-6.5",
  file: "M7 3h7l5 5v13H7V3zm7 0v5h5M10 13h6M10 17h4",
  wallet: "M4 7.5h15a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7.5zm0 0L15 4v3.5M16 14h.01",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "size-5", filled = false }: { name: IconName; className?: string; filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      focusable="false"
      className={className}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
