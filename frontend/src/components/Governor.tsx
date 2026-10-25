import { useEffect, useMemo, useRef, useState } from "react";
import { api, type GovernorView, type PerfMode, type ResourceSample } from "../api";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";
import { Icon } from "./Icons";

const MODES: PerfMode[] = ["silent", "balanced", "turbo"];
const WINDOW_S = 300; // charts show the last 5 minutes

type T = ReturnType<typeof useI18n>["t"];

/** "Paused: game detected" etc. */
export function governorLabel(g: GovernorView, t: T): string {
  if (g.state === "paused") return t(`gov.paused.${g.reason ?? "busy"}`);
  if (g.state === "cooling") return t("gov.state.cooling");
  if (g.state === "waiting_idle") return t("gov.state.waiting_idle");
  if (g.override) return t("gov.state.override");
  if (g.state === "idle") return t("gov.state.idle");
  if (g.state === "running" && g.away) return t("gov.state.away");
  if (g.state === "running") return t("gov.state.full");
  return t("gov.state.running");
}

const gb = (mb: number | null | undefined, digits = 1) => (mb == null ? "–" : (mb / 1024).toFixed(digits));

function tone(g: GovernorView): "ok" | "wait" | "warn" {
  if (g.state === "cooling") return "warn";
  if (g.state === "paused" || g.state === "waiting_idle") return "wait";
  return "ok";
}

function hot(g: GovernorView): { temp: boolean; vram: boolean } {
  const s = g.sample;
  const limit = g.limits?.gpu_temp ?? 85;
  const temp = s?.gpu_temp != null && s.gpu_temp >= limit - 5;
  const total = s?.vram_total_mb ?? 0;
  const head = g.limits?.vram_headroom_mb ?? 0;
  const vram = s?.vram_used_mb != null && total > 0 && s.vram_used_mb >= total - head;
  return { temp, vram };
}

/** Top bar: status pill + live numbers; click opens the resource monitor. */
export function GovernorWidget() {
  const { t, num } = useI18n();
  const { governor: g, history, jobs } = useJobs();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!g || g.state === "off") return null;
  const s = g.sample;
  const tn = tone(g);
  const warn = hot(g);
  const working = jobs.some((j) => j.status === "running");
  const resume = () => api.resumeAnyway().catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));

  return (
    <div className="gov" ref={ref}>
      <button
        type="button"
        className={`gov-pill gov-${tn}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
        title={t("gov.open")}
      >
        <span className={`gov-dot${tn === "ok" && working ? " pulse" : ""}`} aria-hidden />
        <span className="gov-mode">{t(`gov.mode.${g.mode}`)}</span>
        <span className="gov-state">{governorLabel(g, t)}</span>
        {s && (
          <span className="gov-nums mono">
            <span>
              {t("gov.cpu")} {num(Math.round(s.cpu))}%
            </span>
            {s.gpu != null && (
              <span>
                {t("gov.gpu")} {num(Math.round(s.gpu))}%
              </span>
            )}
            {s.vram_total_mb != null && (
              <span className={warn.vram ? "is-warn" : undefined}>
                {gb(s.vram_used_mb)}/{gb(s.vram_total_mb, 0)} GB
              </span>
            )}
            {s.gpu_temp != null && <span className={warn.temp ? "is-warn" : undefined}>{num(s.gpu_temp)}°</span>}
          </span>
        )}
      </button>
      {g.paused && working && (
        <button type="button" className="btn btn-sm gov-resume" onClick={resume}>
          <Icon name="play" size={14} />
          {t("gov.resume")}
        </button>
      )}
      {open && <GovernorPanel g={g} history={history} onResume={resume} />}
    </div>
  );
}

function GovernorPanel({ g, history, onResume }: { g: GovernorView; history: ResourceSample[]; onResume: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs } = useJobs();
  const [mode, setMode] = useState<PerfMode>(g.mode);
  useEffect(() => setMode(g.mode), [g.mode]);
  const s = g.sample;
  const warn = hot(g);
  const working = jobs.some((j) => j.status === "running");
  const choose = (m: PerfMode) => {
    setMode(m);
    api.setPerfMode(m).catch((e) => {
      setMode(g.mode);
      toast({ kind: "err", text: e.message, hint: e.hint });
    });
  };
  const total = s?.vram_total_mb ?? null;
  const budgetLine = total != null && g.limits?.vram_headroom_mb != null ? total - g.limits.vram_headroom_mb : null;
  const tempLimit = g.limits?.gpu_temp ?? 85;

  return (
    <div className="gov-panel" role="dialog" aria-label={t("gov.title")}>
      <div className="gov-panel-head">
        <div>
          <div className="gov-title">{t("gov.title")}</div>
          <div className={`gov-status gov-${tone(g)}`}>
            <span className="gov-dot" aria-hidden />
            {governorLabel(g, t)}
            {g.detail && g.state === "paused" && <span className="muted mono"> · {g.detail}</span>}
          </div>
        </div>
        {g.paused && working && (
          <button type="button" className="btn btn-sm" onClick={onResume}>
            <Icon name="play" size={14} />
            {t("gov.resume")}
          </button>
        )}
      </div>

      <div className="segmented block gov-modes" role="radiogroup" aria-label={t("gov.mode_label")}>
        {MODES.map((m) => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} aria-pressed={mode === m} onClick={() => choose(m)}>
            {t(`gov.mode.${m}`)}
          </button>
        ))}
      </div>
      <p className="gov-desc muted">{t(`gov.mode_desc.${mode}`)}</p>

      <div className="gov-legend" aria-hidden>
        <span>
          <i className="sw sw-ours" />
          SharkyClips
        </span>
        <span>
          <i className="sw sw-other" />
          {t("gov.other_apps")}
        </span>
      </div>

      <div className="gov-charts">
        <MiniChart
          title={t("gov.cpu")}
          now={s ? `${num(Math.round(s.cpu))}%` : "–"}
          sub={s ? t("gov.ours_pct", { n: num(Math.round(s.cpu_ours)) }) : undefined}
          history={history}
          max={100}
          total={(r) => r.cpu}
          ours={(r) => r.cpu_ours}
          fmt={(v) => `${num(Math.round(v))}%`}
        />
        <MiniChart
          title={t("gov.gpu")}
          now={s?.gpu != null ? `${num(Math.round(s.gpu))}%` : "–"}
          sub={s?.gpu_ours != null ? t("gov.ours_pct", { n: num(Math.round(s.gpu_ours)) }) : undefined}
          history={history}
          max={100}
          total={(r) => r.gpu}
          ours={(r) => r.gpu_ours}
          fmt={(v) => `${num(Math.round(v))}%`}
        />
        <MiniChart
          title={t("gov.vram")}
          now={s?.vram_used_mb != null ? `${gb(s.vram_used_mb)} / ${gb(total, 0)} GB` : "–"}
          sub={s?.vram_ours_mb != null ? t("gov.ours_gb", { n: gb(s.vram_ours_mb) }) : undefined}
          warn={warn.vram}
          history={history}
          max={total ?? 1}
          limit={budgetLine}
          limitLabel={t("gov.vram_limit")}
          total={(r) => r.vram_used_mb}
          ours={(r) => r.vram_ours_mb}
          fmt={(v) => `${gb(v)} GB`}
        />
        <MiniChart
          title={t("gov.temp")}
          now={s?.gpu_temp != null ? `${num(s.gpu_temp)} °C` : "–"}
          sub={t("gov.temp_limit", { n: num(tempLimit) })}
          warn={warn.temp}
          history={history}
          max={Math.max(100, tempLimit + 5)}
          min={30}
          limit={tempLimit}
          limitLabel={t("gov.temp_limit_short")}
          total={(r) => r.gpu_temp}
          fmt={(v) => `${num(Math.round(v))} °C`}
        />
      </div>

      {s && (
        <div className="gov-ram">
          <span>{t("gov.ram")}</span>
          <span className="mono">
            {gb(s.ram_used_mb)} / {gb(s.ram_total_mb, 0)} GB
            <span className="muted"> · SharkyClips {gb(s.ram_ours_mb)} GB</span>
          </span>
        </div>
      )}
      <div className="gov-foot">
        <span className="muted">
          {g.sensors?.gpu_name ?? t("gov.no_gpu")}
          {g.cores ? ` · ${t("gov.cores", { n: num(g.cores), total: num(g.cpu_count ?? g.cores) })}` : ""}
        </span>
        <a href={href.settings}>{t("gov.settings")}</a>
      </div>
    </div>
  );
}

const W = 300;
const H = 64;

/** Stacked area: SharkyClips (bottom) + other apps (top) = total; or a single line. */
function MiniChart(props: {
  title: string;
  now: string;
  sub?: string;
  warn?: boolean;
  history: ResourceSample[];
  max: number;
  min?: number;
  limit?: number | null;
  limitLabel?: string;
  total: (r: ResourceSample) => number | null;
  ours?: (r: ResourceSample) => number | null;
  fmt: (v: number) => string;
}) {
  const { t } = useI18n();
  const { history, max, min = 0, total, ours, fmt } = props;
  const [hover, setHover] = useState<number | null>(null);
  const end = history.length ? history[history.length - 1].t : 0;
  const pts = useMemo(
    () => history.filter((r) => end - r.t <= WINDOW_S && total(r) != null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [history, end],
  );
  const x = (tt: number) => W - ((end - tt) / WINDOW_S) * W;
  const y = (v: number) => H - (Math.max(0, Math.min(1, (v - min) / (max - min || 1))) * (H - 4) + 1);

  const path = (vals: (r: ResourceSample) => number) =>
    pts.map((r, i) => `${i ? "L" : "M"}${x(r.t).toFixed(1)},${y(vals(r)).toFixed(1)}`).join("");
  const area = (top: (r: ResourceSample) => number, bottom: (r: ResourceSample) => number) => {
    if (pts.length < 2) return "";
    const up = pts.map((r, i) => `${i ? "L" : "M"}${x(r.t).toFixed(1)},${y(top(r)).toFixed(1)}`).join("");
    const down = [...pts].reverse().map((r) => `L${x(r.t).toFixed(1)},${y(bottom(r)).toFixed(1)}`).join("");
    return `${up}${down}Z`;
  };
  const tot = (r: ResourceSample) => total(r) ?? 0;
  const our = (r: ResourceSample) => Math.min(tot(r), ours?.(r) ?? 0);

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!pts.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const tx = end - (1 - (e.clientX - rect.left) / rect.width) * WINDOW_S;
    let best = 0;
    for (let i = 1; i < pts.length; i++) if (Math.abs(pts[i].t - tx) < Math.abs(pts[best].t - tx)) best = i;
    setHover(best);
  };
  const h = hover != null ? pts[hover] : null;
  const ago = h ? Math.round(end - h.t) : 0;

  return (
    <figure className={`gov-chart${props.warn ? " is-warn" : ""}`}>
      <figcaption>
        <span className="gov-chart-title">
          {props.warn && <Icon name="alert" size={13} />}
          {props.title}
        </span>
        <span className="mono gov-chart-now">{props.now}</span>
      </figcaption>
      <div className="gov-chart-plot">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
          role="img"
          aria-label={`${props.title}: ${props.now}`}
        >
          <line x1="0" x2={W} y1={H - 0.5} y2={H - 0.5} className="gov-axis" />
          {ours ? (
            <>
              <path d={area(tot, our)} className="gov-area-other" />
              <path d={area(our, () => min)} className="gov-area-ours" />
              <path d={path(tot)} className="gov-line-total" />
            </>
          ) : (
            <path d={path(tot)} className={`gov-line-single${props.warn ? " is-warn" : ""}`} />
          )}
          {props.limit != null && (
            <line x1="0" x2={W} y1={y(props.limit)} y2={y(props.limit)} className="gov-limit" />
          )}
          {h && <line x1={x(h.t)} x2={x(h.t)} y1="0" y2={H} className="gov-cross" />}
        </svg>
        {h && (
          <div className="gov-tip" style={{ insetInlineStart: `${Math.min(70, Math.max(0, (x(h.t) / W) * 100 - 15))}%` }}>
            <div className="muted">{ago < 3 ? t("gov.now") : t("gov.ago", { s: ago })}</div>
            {ours ? (
              <>
                <div>
                  <i className="sw sw-ours" />
                  SharkyClips <b className="mono">{fmt(our(h))}</b>
                </div>
                <div>
                  <i className="sw sw-other" />
                  {t("gov.other_apps")} <b className="mono">{fmt(Math.max(0, tot(h) - our(h)))}</b>
                </div>
              </>
            ) : (
              <div>
                <b className="mono">{fmt(tot(h))}</b>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="gov-chart-foot muted">
        <span>{props.sub}</span>
        {props.limit != null && props.limitLabel && <span className="gov-limit-key">{props.limitLabel}</span>}
      </div>
    </figure>
  );
}
