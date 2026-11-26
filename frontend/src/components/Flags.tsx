// Flags for the language switcher (1.2.53). Artwork with fixed national colours, the one place
// besides themes.css / PlatformIcons.tsx that may hold colour values (test_theme_tokens.py).

/**
 * 1.2.53: the language switcher (top bar + home screen): flag + language name.
 * Flags are small inline SVGs (Windows has no flag emoji). A flag stands for the language, not a
 * country: English = GB, Portuguese = Brazil, Arabic = Saudi Arabia, Spanish = Spain.
 */
export function Flag({ code, size = 18 }: { code: string; size?: number }) {
  const h = Math.round((size * 2) / 3);
  const common = { width: size, height: h, viewBox: "0 0 30 20", "aria-hidden": true, focusable: false, className: "flag" } as const;
  switch (code) {
    case "gb":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#012169" />
          <path d="M0 0L30 20M30 0L0 20" stroke="#fff" strokeWidth="4" />
          <path d="M0 0L30 20M30 0L0 20" stroke="#C8102E" strokeWidth="1.6" />
          <path d="M15 0V20M0 10H30" stroke="#fff" strokeWidth="6" />
          <path d="M15 0V20M0 10H30" stroke="#C8102E" strokeWidth="3.4" />
        </svg>
      );
    case "tr":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#E30A17" />
          <circle cx="11" cy="10" r="5" fill="#fff" />
          <circle cx="12.3" cy="10" r="4" fill="#E30A17" />
          <path d="M16.2 10l3.6-1.2-2.2 3.1V8.1l2.2 3.1z" fill="#fff" />
        </svg>
      );
    case "es":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#AA151B" />
          <rect y="5" width="30" height="10" fill="#F1BF00" />
        </svg>
      );
    case "br":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#009C3B" />
          <path d="M15 2.5L27 10 15 17.5 3 10z" fill="#FFDF00" />
          <circle cx="15" cy="10" r="4.2" fill="#002776" />
        </svg>
      );
    case "ru":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#fff" />
          <rect y="6.67" width="30" height="6.67" fill="#0039A6" />
          <rect y="13.33" width="30" height="6.67" fill="#D52B1E" />
        </svg>
      );
    case "de":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#000" />
          <rect y="6.67" width="30" height="6.67" fill="#DD0000" />
          <rect y="13.33" width="30" height="6.67" fill="#FFCE00" />
        </svg>
      );
    case "fr":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#fff" />
          <rect width="10" height="20" fill="#002395" />
          <rect x="20" width="10" height="20" fill="#ED2939" />
        </svg>
      );
    case "sa":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#006C35" />
          <path d="M8 8.5h14M9 10.5h12" stroke="#fff" strokeWidth="1" />
          <path d="M9 14h12" stroke="#fff" strokeWidth="1.2" />
        </svg>
      );
    case "cn":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#DE2910" />
          <path d="M6 3l1.2 3.6H11L8 8.8l1.1 3.6L6 10.2 2.9 12.4 4 8.8 1 6.6h3.8z" fill="#FFDE00" />
        </svg>
      );
    case "jp":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#fff" stroke="#ddd" strokeWidth="0.6" />
          <circle cx="15" cy="10" r="5.5" fill="#BC002D" />
        </svg>
      );
    case "hu":
      return (
        <svg {...common}>
          <rect width="30" height="20" fill="#CD2A3E" />
          <rect y="6.67" width="30" height="6.67" fill="#fff" />
          <rect y="13.33" width="30" height="6.67" fill="#436F4D" />
        </svg>
      );
    default:
      return null;
  }
}
