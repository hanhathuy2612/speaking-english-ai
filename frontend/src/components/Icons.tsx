// Inline SVG icons (no icon library, the app works offline). All are decorative: aria-hidden.
type P = { size?: number };

const stroke = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

export const ChatIcon = ({ size = 18 }: P) => (
  <svg {...stroke(size)}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

export const MicIcon = ({ size = 26 }: P) => (
  <svg {...stroke(size)}>
    <rect x="9" y="2" width="6" height="12" rx="3" />
    <path d="M5 10a7 7 0 0 0 14 0M12 17v5" />
  </svg>
);

export const PlayIcon = ({ size = 14 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M8 5v14l11-7z" />
  </svg>
);

export const UndoIcon = ({ size = 15 }: P) => (
  <svg {...stroke(size)}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
  </svg>
);

export const BulbIcon = ({ size = 16 }: P) => (
  <svg {...stroke(size)}>
    <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V16h8v-1.3A7 7 0 0 0 12 2z" />
  </svg>
);

export const CheckIcon = ({ size = 12, width = 3.5 }: P & { width?: number }) => (
  <svg {...stroke(size)} strokeWidth={width}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const ChevronIcon = ({ size = 16 }: P) => (
  <svg {...stroke(size)} className="chevron">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const TrashIcon = ({ size = 15 }: P) => (
  <svg {...stroke(size)}>
    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
  </svg>
);

export const XIcon = ({ size = 12, width = 3.5 }: P & { width?: number }) => (
  <svg {...stroke(size)} strokeWidth={width}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const StopIcon = ({ size = 22 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
);

export const MenuIcon = ({ size = 18 }: P) => (
  <svg {...stroke(size)}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

export const SpeakerIcon = ({ size = 16 }: P) => (
  <svg {...stroke(size)}>
    <path d="M11 5 6 9H2v6h4l5 4z" />
    <path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" />
  </svg>
);

export const LockIcon = ({ size = 14 }: P) => (
  <svg {...stroke(size)}>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);
