import { useId } from "react";

// The SharkyClips mark: a shark fin above a water line, with a play triangle cut out of the fin.
// Same geometry as installer/make_icons.py (64 x 64 grid) - change both together.
export const FIN_PATH =
  "M13 44C17.5 33 28 18 48.5 11.5C42 20 39.5 32 46.5 44ZM25.5 30L25.5 40.5L35 35.25Z";
export const WAVE_PATH =
  "M8 50Q11 48.4 14 50Q17 51.6 20 50Q23 48.4 26 50Q29 51.6 32 50Q35 48.4 38 50Q41 51.6 44 50Q47 48.4 50 50Q53 51.6 56 50";
// A long wave for the animated splash (drifts by one 12-unit period, seamless).
export const LONG_WAVE =
  "M-12 50q3-1.6 6 0" + " t6 0".repeat(29);

/** Header / small uses. Colors come from CSS (--mark-fin, --mark-wave), so it follows the theme. */
export function BrandMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="6 8 52 48" aria-hidden="true" className="brand-svg">
      <path fillRule="evenodd" d={FIN_PATH} fill="var(--mark-fin)" />
      <path d={WAVE_PATH} fill="none" stroke="var(--mark-wave)" strokeWidth="3.4" strokeLinecap="round" />
    </svg>
  );
}

/** The blue-and-white mark with the gradient fin; `animated`: the fin glides in, the water drifts. */
export function SharkLogo({ animated = false, className }: { animated?: boolean; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={className} viewBox="0 0 160 64" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-fin`} x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" stopColor="#1F6FE5" />
          <stop offset="1" stopColor="#0F3A94" />
        </linearGradient>
        <clipPath id={`${id}-sea`}>
          <rect x="0" y="40" width="160" height="24" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id}-sea)`}>
        <path
          className={animated ? "logo-waves" : undefined}
          d={LONG_WAVE}
          fill="none"
          stroke="#A9C6F3"
          strokeWidth="2.6"
          strokeLinecap="round"
        />
      </g>
      <g transform="translate(49 0)">
        <g className={animated ? "logo-fin" : undefined}>
          <path fillRule="evenodd" d={FIN_PATH} fill={`url(#${id}-fin)`} />
        </g>
      </g>
    </svg>
  );
}
