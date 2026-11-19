const PATHS = {
  dashboard: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  orders: "M6 3h12v18H6zM9 8h6M9 12h6M9 16h4",
  trips: "M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19.5v.01M17 19.5v.01",
  customers: "M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1",
  board: "M3 4h18v16H3zM9 4v16M15 4v16",
  job: "M3 8h18v12H3zM9 8V5h6v3M3 13h18",
  timeline: "M3 6h10M7 12h14M3 18h8M15 18h6",
  route: "M5 19v.01M19 5v.01M7 18h6a3 3 0 0 0 0-6h-2a3 3 0 0 1 0-6h6",
  fleet: "M2 17h20M4 17V9h9v8M13 12h5l3 3v2",
  pricing: "M4 4h9l7 7-9 9-7-7zM8.5 8.5v.01",
  settings: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
  chevronLeft: "M15 6l-6 6 6 6",
  chevronRight: "M9 6l6 6-6 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 6l12 12M18 6L6 18",
} as const;

export type IconName = keyof typeof PATHS;

/** Decorative icon: the meaning is always carried by adjacent or visually hidden text. */
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
