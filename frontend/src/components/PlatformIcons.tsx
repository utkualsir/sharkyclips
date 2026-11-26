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

/** Google's "G" (multicolor, as Google's sign-in branding asks). */
export function GoogleG({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
