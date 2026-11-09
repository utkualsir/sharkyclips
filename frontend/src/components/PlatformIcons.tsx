// 1.2.36: the three platforms' own marks (inline SVG, no network) + their accent colours.
import { useId } from "react";
import type { Target } from "../multipost";

const TT = "M16.6 5.8a4.3 4.3 0 0 1-1-2.8h-3.1v12.4a2.6 2.6 0 1 1-2.6-2.6c.3 0 .5 0 .8.1V9.7a5.7 5.7 0 1 0 4.9 5.7V9.1a7.3 7.3 0 0 0 4.3 1.4V7.4a4.3 4.3 0 0 1-3.3-1.6z";

export function PlatformIcon({ p, size = 18 }: { p: Target; size?: number }) {
  const gid = useId().replace(/:/g, "");
  if (p === "youtube") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="pf-icon">
        <rect x="1.5" y="5" width="21" height="14.5" rx="4.2" fill="#FF0000" />
        <path d="M10 8.9v6.7l5.8-3.35z" fill="#fff" />
      </svg>
    );
  }
  if (p === "tiktok") {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="pf-icon pf-icon-tt">
        <path d={TT} fill="#25F4EE" transform="translate(-0.7 -0.6)" />
        <path d={TT} fill="#FE2C55" transform="translate(0.7 0.6)" />
        <path d={TT} fill="var(--pf-tt-ink, currentColor)" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="pf-icon">
      <defs>
        <linearGradient id={`ig${gid}`} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#FEDA75" />
          <stop offset="0.35" stopColor="#FA7E1E" />
          <stop offset="0.6" stopColor="#D62976" />
          <stop offset="0.85" stopColor="#962FBF" />
          <stop offset="1" stopColor="#4F5BD5" />
        </linearGradient>
      </defs>
      <rect x="3" y="3" width="18" height="18" rx="5.2" fill="none" stroke={`url(#ig${gid})`} strokeWidth="2.1" />
      <circle cx="12" cy="12" r="4.1" fill="none" stroke={`url(#ig${gid})`} strokeWidth="2.1" />
      <circle cx="17.3" cy="6.7" r="1.25" fill={`url(#ig${gid})`} />
    </svg>
  );
}
