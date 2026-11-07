import { useEffect, useMemo, useRef, useState } from "react";
import { api, type ClipEdit, type EditPlanView, type SwearItem, type SwearScanView } from "../api";
import { useJobs } from "../jobs";
import { mergeRanges, speakerLabel, subtractRange } from "../editing";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";

interface Props {
  projectId: string;
  plan: EditPlanView | null;
  edit: ClipEdit | undefined;
  lang: string | null;
  onChange: (edit: ClipEdit) => void;
  /** play [t0, t1] of the source in the preview */
  onPlay: (t0: number, t1: number) => void;
}

/** Bleep on / off for one range: drop it from one list, add it to the other. */
export function toggleBleep(edit: ClipEdit | undefined, a: number, b: number, on: boolean): ClipEdit {
  const bleep = edit?.bleep ?? [];
  const unbleep = edit?.unbleep ?? [];
  return on
    ? { ...edit, bleep: mergeRanges([...bleep, [a, b]]), unbleep: subtractRange(unbleep, a - 0.02, b + 0.02) }
    : { ...edit, bleep: subtractRange(bleep, a - 0.02, b + 0.02), unbleep: mergeRanges([...unbleep, [a, b]]) };
}

/** Every swear the render bleeps (or might): speaker, time, a play button and a switch. A
 * waveform of the clip shows the bleeps; drag across it to bleep any moment by hand. */
export default function SwearReview({ projectId, plan, edit, lang, onChange, onPlay }: Props) {
  const { t, num } = useI18n();
  const items = plan?.swears ?? [];
  const on = items.filter((s) => s.bleep).length;
  const maybe = items.filter((s) => s.status === "maybe" && !s.bleep).length;
  const [peaks, setPeaks] = useState<number[]>([]);
  const [scan, setScan] = useState<SwearScanView | null>(null);
  const { jobs } = useJobs();
  const scanJob = jobs.find((j) => j.kind === "swearscan" && j.project_id === projectId && (j.status === "queued" || j.status === "running"));
  useEffect(() => {
    let cancelled = false;
    api
      .swearScan(projectId)
      .then((s) => !cancelled && setScan(s))
      .catch(() => !cancelled && setScan(null));
    return () => {
      cancelled = true;
    };
  }, [projectId, !!scanJob]);
  const [sel, setSel] = useState<[number, number] | null>(null);
  const drag = useRef<number | null>(null);
  const strip = useRef<HTMLDivElement>(null);
  const start = plan?.start ?? 0;
  const end = plan?.end ?? 0;
  const dur = Math.max(0.1, end - start);

  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    api
      .peaks(projectId, start, end, 360)
      .then((p) => !cancelled && setPeaks(p.peaks))
      .catch(() => !cancelled && setPeaks([]));
    return () => {
      cancelled = true;
    };
  }, [projectId, plan?.clip_id, Math.round(start * 10), Math.round(end * 10)]); // eslint-disable-line react-hooks/exhaustive-deps

  const bleeped = useMemo(() => items.filter((s) => s.bleep), [items]);
  if (!plan) return null;

  const at = (clientX: number) => {
    const r = strip.current!.getBoundingClientRect();
    return start + Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * dur;
  };
  const pct = (v: number) => `${((v - start) / dur) * 100}%`;
  const name = (spk: string | null) => (spk ? speakerLabel(spk, plan.speakers, t) : t("swear.someone"));
  const why = (s: SwearItem) => {
    const k = s.why.startsWith("scan") ? "scan" : s.why.split("+")[0];
    const base = t(`swear.why.${k}`);
    const heard = s.heard && s.heard.length > 1 ? ` · ${s.heard.slice(0, 4).join(", ")}` : "";
    return s.votes ? `${base} (${t("swear.votes", { v: s.votes })})${heard}` : base;
  };

  return (
    <section className="panel swear-review" aria-labelledby="swear-title">
      <div className="panel-head">
        <h2 className="section-title" id="swear-title">
          {t("swear.title")}
        </h2>
        <span className="muted small">
          {plan.bleep_mode === "off"
            ? t("swear.off")
            : t("swear.summary", { n: num(on), m: num(maybe) })}
        </span>
      </div>
      <div className="swear-scan">
        <span className="muted small">
          {scanJob
            ? t(`stage.${scanJob.stage ?? "swears_listening"}`)
            : scan?.done
              ? t(scan.stale ? "swear.scan_stale" : "swear.scan_done", { n: num(scan.items?.length ?? 0) })
              : t("swear.scan_hint")}
        </span>
        {!scanJob && (
          <button className="btn btn-sm btn-ghost" onClick={() => api.runSwearScan(projectId).catch(() => undefined)}>
            <Icon name="scan" />
            {scan?.done ? t("swear.scan_again") : t("swear.scan")}
          </button>
        )}
      </div>
      <div
        className="swear-wave"
        ref={strip}
        role="slider"
        aria-label={t("swear.wave")}
        aria-valuemin={0}
        aria-valuemax={Math.round(dur)}
        aria-valuenow={0}
        tabIndex={0}
        title={t("swear.wave_hint")}
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          const x = at(e.clientX);
          drag.current = x;
          setSel([x, x]);
        }}
        onPointerMove={(e) => {
          if (drag.current == null) return;
          const x = at(e.clientX);
          setSel([Math.min(drag.current, x), Math.max(drag.current, x)]);
        }}
        onPointerUp={(e) => {
          if (drag.current == null) return;
          const x = at(e.clientX);
          const a = Math.min(drag.current, x);
          const b = Math.max(drag.current, x);
          drag.current = null;
          if (b - a < 0.08) {
            setSel(null);
            onPlay(Math.max(start, a - 0.3), Math.min(end, a + 1.5));
          } else setSel([a, b]);
        }}
      >
        <div className="swear-bars" aria-hidden="true">
          {peaks.map((p, i) => (
            <i key={i} style={{ height: `${Math.max(4, p * 100)}%` }} />
          ))}
        </div>
        {bleeped.map((s, i) => (
          <span key={i} className={`swear-mark${s.status === "manual" ? " manual" : ""}`} style={{ left: pct(s.start), width: `${((s.end - s.start) / dur) * 100}%` }} />
        ))}
        {items
          .filter((s) => !s.bleep)
          .map((s, i) => (
            <span key={`m${i}`} className="swear-mark maybe" style={{ left: pct(s.start), width: `${((s.end - s.start) / dur) * 100}%` }} />
          ))}
        {sel && sel[1] - sel[0] >= 0.08 && (
          <span className="swear-sel" style={{ left: pct(sel[0]), width: `${((sel[1] - sel[0]) / dur) * 100}%` }} />
        )}
      </div>
      <div className="swear-wave-actions">
        <span className="muted small">{sel && sel[1] - sel[0] >= 0.08 ? `${fmtTime(sel[0], true)} – ${fmtTime(sel[1], true)}` : t("swear.wave_hint")}</span>
        {sel && sel[1] - sel[0] >= 0.08 && (
          <>
            <button className="btn btn-sm btn-ghost" onClick={() => onPlay(sel[0] - 0.4, sel[1] + 0.4)}>
              <Icon name="play" />
              {t("swear.play")}
            </button>
            <button
              className="btn btn-sm"
              onClick={() => {
                onChange(toggleBleep(edit, sel[0], sel[1], true));
                setSel(null);
              }}
            >
              {t("swear.bleep_range")}
            </button>
          </>
        )}
      </div>
      {items.length === 0 ? (
        <p className="muted small" style={{ margin: 0 }}>
          {t("swear.none")}
        </p>
      ) : (
        <ul className="swear-list" lang={lang ?? undefined}>
          {items.map((s, i) => (
            <li key={`${s.start}-${i}`} className={s.bleep ? "on" : ""}>
              <button className="btn btn-sm btn-ghost icon-btn" onClick={() => onPlay(s.start - 0.8, s.end + 0.8)} aria-label={t("swear.play")} title={t("swear.play")}>
                <Icon name="play" />
              </button>
              <span className="tc muted">{fmtTime(s.start, true)}</span>
              <span className={`spk-chip spk-${s.spk ?? "none"}`}>{name(s.spk)}</span>
              <span className="swear-word" dir="auto">
                {s.word || "…"}
              </span>
              <span className={`badge swear-${s.status}`} title={why(s)}>
                {t(`swear.status.${s.status}`)}
              </span>
              <label className="swear-switch">
                <input
                  type="checkbox"
                  checked={s.bleep}
                  onChange={(e) => onChange(toggleBleep(edit, s.start, s.end, e.target.checked))}
                />
                <span>{t("swear.bleep")}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
