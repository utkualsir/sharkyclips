import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { EasyStep, EasyStepKey, Mode } from "../api";
import { useI18n } from "../i18n";
import { useUiMode } from "../uimode";
import { Icon } from "./Icons";

// Shared pieces of Easy mode: the friendly progress list, the content-type chip, the Pro switch
// and the 3-step first-run tour.

export const MODE_ICON: Record<Mode, string> = { gaming: "gamepad", study: "book", music: "music" };
const STEP_ICON: Record<EasyStepKey, string> = {
  download: "download",
  transcribe: "message",
  find: "sparkles",
  titles: "wand",
  render: "film",
};

export function fmtEtaWords(sec: number | null | undefined, t: ReturnType<typeof useI18n>["t"], num: (n: number) => string): string | null {
  if (sec == null) return null;
  if (sec < 60) return t("easy.eta_soon");
  const min = Math.round(sec / 60);
  if (min < 60) return t("easy.eta_min", { n: num(min) });
  return t("easy.eta_hours", { h: num(Math.floor(min / 60)), m: num(min % 60) });
}

/** "Downloading the video -> Writing down what's said -> Looking for the best moments -> ..." */
export function EasyProgress({ steps, eta, compact }: { steps: EasyStep[]; eta: number | null; compact?: boolean }) {
  const { t, num } = useI18n();
  const etaText = fmtEtaWords(eta, t, num);
  return (
    <section className={`ez-progress${compact ? " compact" : ""}`} aria-labelledby="ez-progress-title">
      <div className="ez-progress-head">
        <h2 id="ez-progress-title">{t("easy.progress_title")}</h2>
        {etaText && (
          <span className="ez-eta">
            <Icon name="clock" size={15} /> {etaText}
          </span>
        )}
      </div>
      <ol className="ez-steps">
        {steps.map((s) => (
          <li key={s.key} className={`ez-step ez-step-${s.status}`} aria-current={s.status === "active" ? "step" : undefined}>
            <span className="ez-step-dot" aria-hidden="true">
              {s.status === "done" ? (
                <Icon name="check" size={16} />
              ) : s.status === "active" ? (
                <span className="spinner" />
              ) : (
                <Icon name={STEP_ICON[s.key]} size={16} />
              )}
            </span>
            <span className="ez-step-text">
              {t(`easy.step.${s.key}`)}
              <span className="sr-only"> · {t(`easy.step_status.${s.status}`)}</span>
            </span>
            {s.status === "active" && s.progress != null && (
              <span className="ez-step-pct mono">{num(Math.round(s.progress * 100))}%</span>
            )}
          </li>
        ))}
      </ol>
      {!compact && (
        <p className="ez-note">
          <Icon name="check" size={14} /> {t("easy.close_note")}
        </p>
      )}
    </section>
  );
}

/** Small changeable chip: the detected content type (gaming / study / music) or "detect". */
export function ModeChip({
  value,
  onChange,
  auto,
  allowAuto,
  disabled,
}: {
  value: Mode | "auto";
  onChange: (m: Mode | "auto") => void;
  auto?: boolean;
  allowAuto?: boolean;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const opts: (Mode | "auto")[] = allowAuto ? ["auto", "gaming", "study", "music"] : ["gaming", "study", "music"];
  return (
    <label className="ez-chip">
      <Icon name={value === "auto" ? "sparkles" : MODE_ICON[value]} size={14} />
      <span className="sr-only">{t("easy.content_type")}</span>
      <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value as Mode | "auto")} aria-label={t("easy.content_type")}>
        {opts.map((m) => (
          <option key={m} value={m}>
            {m === "auto" ? t("easy.mode_auto") : t(`mode.${m}`)}
          </option>
        ))}
      </select>
      {auto && value !== "auto" && <span className="ez-chip-note">{t("easy.detected")}</span>}
      <Icon name="chevron-down" size={13} />
    </label>
  );
}

/** "Pro mode" switch in the top bar (remembered). */
export function ProSwitch() {
  const { t } = useI18n();
  const { mode, setMode } = useUiMode();
  const pro = mode === "pro";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={pro}
      className={`pro-switch${pro ? " on" : ""}`}
      onClick={() => {
        setMode(pro ? "easy" : "pro");
        window.location.hash = "#/";
      }}
      title={pro ? t("easy.switch_to_easy") : t("easy.switch_to_pro")}
      data-tour="pro"
    >
      <span className="pro-switch-track" aria-hidden="true">
        <span className="pro-switch-knob" />
      </span>
      <span className="pro-switch-label">{t("easy.pro_mode")}</span>
    </button>
  );
}

// ---------------------------------------------------------------- first-run tour (3 tooltips)

const TOUR = ["drop", "find", "pro"] as const;

export function EasyTour({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [i, setI] = useState(0);
  const [box, setBox] = useState<{ top: number; left: number; width: number; below: boolean } | null>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const step = TOUR[i];

  useLayoutEffect(() => {
    const place = () => {
      const el = document.querySelector<HTMLElement>(`[data-tour="${step}"]`);
      if (!el) {
        setBox(null);
        return;
      }
      const r = el.getBoundingClientRect();
      const w = Math.min(320, window.innerWidth - 32);
      const below = r.bottom + 180 < window.innerHeight || r.top < 200;
      const left = Math.max(16, Math.min(window.innerWidth - w - 16, r.left + r.width / 2 - w / 2));
      setBox({ top: below ? r.bottom + 12 : r.top - 12, left, width: w, below });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [step]);

  useEffect(() => {
    tipRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onDone();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [i, onDone]);

  const last = i === TOUR.length - 1;
  return (
    <div
      ref={tipRef}
      className={`ez-tip${box?.below === false ? " above" : ""}`}
      role="dialog"
      aria-modal="false"
      aria-labelledby="ez-tip-title"
      tabIndex={-1}
      style={box ? { top: box.top, left: box.left, width: box.width } : { top: 96, insetInlineEnd: 16, width: 300 }}
    >
      <div className="ez-tip-count mono">
        {i + 1} / {TOUR.length}
      </div>
      <h2 id="ez-tip-title">{t(`easy.tour.${step}_title`)}</h2>
      <p>{t(`easy.tour.${step}_body`)}</p>
      <div className="ez-tip-actions">
        <button className="btn btn-ghost btn-sm" onClick={onDone}>
          {t("easy.tour.skip")}
        </button>
        <button className="btn btn-primary btn-sm" onClick={() => (last ? onDone() : setI(i + 1))}>
          {last ? t("easy.tour.done") : t("easy.tour.next")}
        </button>
      </div>
    </div>
  );
}
