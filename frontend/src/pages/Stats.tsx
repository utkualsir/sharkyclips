import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CalibrationGroup, type CalibrationStats } from "../api";
import { Icon } from "../components/Icons";
import { ProgressBar } from "../components/ui";
import { fmtCompact, fmtInt } from "../format";
import { useI18n, type T } from "../i18n";
import { useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";

type Point = CalibrationStats["points"][number];

export function featureLabel(name: string, t: T): string {
  if (name.startsWith("sig_")) return t(`signal.${name.slice(4)}`);
  const map: Record<string, string> = {
    viral_score: t("publish.viral"),
    hype_score: t("signals.score"),
    hook: t("publish.sub.hook"),
    retention: t("publish.sub.retention"),
    trend_fit: t("publish.sub.trend_fit"),
    length_fit: t("publish.sub.length_fit"),
    duration: t("signals.length"),
    funny: t("stats.f.funny"),
    exciting: t("stats.f.exciting"),
    useful: t("stats.f.useful"),
    self_contained: t("stats.f.self_contained"),
  };
  return map[name] ?? name;
}

// ------------------------------------------------------------------ scatter

function Scatter({ points }: { points: Point[] }) {
  const { t, lang } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  const [hover, setHover] = useState<Point | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pts = points.filter((p) => p.predicted != null);
  const H = 320;
  const m = { l: 56, r: 16, t: 14, b: 42 };
  const vals = pts.flatMap((p) => [Math.max(1, p.views), Math.max(1, p.predicted!)]);
  const lo = Math.floor(Math.log10(Math.min(...vals)));
  const hi = Math.ceil(Math.log10(Math.max(...vals)) + 0.001);
  const span = Math.max(1, hi - lo);
  const iw = Math.max(120, w - m.l - m.r);
  const ih = H - m.t - m.b;
  const x = (v: number) => m.l + ((Math.log10(Math.max(1, v)) - lo) / span) * iw;
  const y = (v: number) => m.t + ih - ((Math.log10(Math.max(1, v)) - lo) / span) * ih;
  const ticks = Array.from({ length: span + 1 }, (_, i) => 10 ** (lo + i));

  return (
    <div className="scatter" ref={box}>
      <svg width={w} height={H} role="img" aria-label={t("stats.chart_title")}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={m.l} x2={m.l + iw} y1={y(v)} y2={y(v)} className="grid" />
            <line x1={x(v)} x2={x(v)} y1={m.t} y2={m.t + ih} className="grid" />
            <text x={m.l - 8} y={y(v)} className="axis-label" textAnchor="end" dominantBaseline="middle">
              {fmtCompact(v, lang)}
            </text>
            <text x={x(v)} y={m.t + ih + 18} className="axis-label" textAnchor="middle">
              {fmtCompact(v, lang)}
            </text>
          </g>
        ))}
        {/* perfect prediction */}
        <line x1={x(ticks[0])} y1={y(ticks[0])} x2={x(ticks[ticks.length - 1])} y2={y(ticks[ticks.length - 1])} className="ideal" />
        <text x={m.l + iw - 4} y={y(ticks[ticks.length - 1]) + 14} className="axis-label" textAnchor="end">
          {t("stats.ideal")}
        </text>
        <text x={m.l + iw / 2} y={H - 4} className="axis-title" textAnchor="middle">
          {t("stats.axis_predicted")}
        </text>
        <text x={14} y={m.t + ih / 2} className="axis-title" textAnchor="middle" transform={`rotate(-90 14 ${m.t + ih / 2})`}>
          {t("stats.axis_real")}
        </text>
        {pts.map((p) => (
          <g key={p.key} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(p)} onBlur={() => setHover(null)} tabIndex={0}>
            <circle cx={x(p.predicted!)} cy={y(p.views)} r={14} fill="transparent" />
            <circle cx={x(p.predicted!)} cy={y(p.views)} r={hover?.key === p.key ? 6.5 : 5} className="dot" />
          </g>
        ))}
      </svg>
      {hover && (
        <div
          className="chart-tip"
          style={{
            left: Math.min(w - 230, Math.max(0, x(hover.predicted!) + 12)),
            top: Math.max(0, y(hover.views) - 70),
          }}
        >
          <div className="tip-title" dir="auto">
            {hover.title}
          </div>
          <div>
            {t("stats.real")}: <b className="mono">{fmtInt(hover.views, lang)}</b>
          </div>
          <div>
            {t("stats.predicted")}: <b className="mono">{fmtInt(hover.predicted!, lang)}</b>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ best-of groups

function Groups({ title, groups, label, note }: { title: string; groups: CalibrationGroup[]; label: (k: string) => string; note?: string }) {
  const { t, lang, num } = useI18n();
  const max = Math.max(1, ...groups.map((g) => g.median_views));
  return (
    <section className="card stat-group">
      <h3>{title}</h3>
      {groups.length === 0 ? (
        <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
          {t("stats.no_data")}
        </p>
      ) : (
        <ul className="bars">
          {groups.map((g, i) => (
            <li key={g.key} title={t("stats.group_tip", { median: fmtInt(g.median_views, lang), n: g.count })}>
              <div className="bar-top">
                <span>
                  {label(g.key)}
                  {i === 0 && groups.length > 1 && <span className="chip chip-gold best-chip">{t("stats.best")}</span>}
                </span>
                <span className="mono">
                  {fmtCompact(g.median_views, lang)} <span className="muted">· {num(g.count)}</span>
                </span>
              </div>
              <div className="sig-bar">
                <span style={{ width: `${Math.max(2, (g.median_views / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
      {note && <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>{note}</p>}
    </section>
  );
}

// ------------------------------------------------------------------ page

export default function Stats() {
  const { t, lang, num, relTime } = useI18n();
  const toast = useToast();
  const { finishedTick } = useJobs();
  const [data, setData] = useState<CalibrationStats | null>(null);

  const load = () => api.calibration().then(setData).catch(() => {});
  useEffect(() => {
    load();
  }, [finishedTick]);

  const st = data?.status;
  const points = data?.points ?? [];
  const sorted = useMemo(() => [...points].sort((a, b) => b.views - a.views), [points]);

  const remove = async (key: string) => {
    await api.deleteCalibrationEntry(key);
    load();
  };
  const clearAll = async () => {
    if (!window.confirm(t("stats.clear_confirm", { n: points.length }))) return;
    const r = await api.clearCalibration();
    toast({ kind: "ok", text: t("stats.cleared", { n: r.removed }) });
    load();
  };

  return (
    <main className="page stats-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("stats.title")}</h1>
          <p className="lede">{t("stats.lede")}</p>
        </div>
        {st && (
          <span className={`chip ${st.calibrated ? "chip-gold" : "chip-outline"} cal-chip`}>
            <Icon name={st.calibrated ? "check" : "clock"} size={13} />
            {st.calibrated ? t("cal.calibrated_n", { n: st.model_points }) : t("cal.default")}
          </span>
        )}
      </div>

      {!data ? (
        <div className="skeleton" style={{ height: 320, borderRadius: 16 }} />
      ) : (
        <>
          <section className="card cal-status">
            {st!.calibrated ? (
              <div className="cal-grid">
                <div>
                  <div className="field-label">{t("stats.how")}</div>
                  <p className="muted" style={{ margin: "4px 0 0" }}>
                    {t("stats.how_calibrated", { n: st!.model_points, w: Math.round(st!.weight * 100) })}
                  </p>
                </div>
                <div>
                  <div className="field-label">{t("stats.accuracy")}</div>
                  <div className="cal-big mono">{st!.r2_loo != null ? `${num(Math.max(0, Math.round(st!.r2_loo * 100)))}%` : "–"}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{t("stats.accuracy_note")}</div>
                </div>
                <div>
                  <div className="field-label">{t("stats.drivers")}</div>
                  <ul className="drivers">
                    {st!.top_features.slice(0, 4).map((f) => (
                      <li key={f.name}>
                        <span>{featureLabel(f.name, t)}</span>
                        <span className={`mono ${f.effect >= 0 ? "ok-text" : "danger-text"}`}>{f.effect >= 0 ? "↑" : "↓"}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="cal-progress">
                <div>
                  <div style={{ fontWeight: 550 }}>{t("cal.progress", { n: st!.n, need: st!.needed })}</div>
                  <p className="muted" style={{ margin: "4px 0 10px" }}>
                    {t("stats.how_default", { need: st!.needed })}
                  </p>
                  <ProgressBar value={Math.min(1, st!.n / st!.needed)} />
                </div>
                <a className="btn btn-sm" href={href.library}>
                  {t("stats.go_enter")}
                </a>
              </div>
            )}
          </section>

          {st!.calibrated && (
            <section className="card" aria-labelledby="chart-title" style={{ padding: 20 }}>
              <div className="panel-head">
                <h2 className="section-title" id="chart-title">
                  {t("stats.chart_title")}
                </h2>
                <span className="muted" style={{ fontSize: 12.5 }}>
                  {t("stats.chart_note")}
                </span>
              </div>
              <Scatter points={points} />
            </section>
          )}

          {points.length > 0 && (
            <div className="stat-groups">
              <Groups title={t("stats.best_mode")} groups={data.best.mode} label={(k) => t(`mode.${k}`)} />
              <Groups
                title={t("stats.best_time")}
                groups={data.best.time}
                label={(k) => t(`stats.time.${k}`)}
                note={data.best.time_basis === "published" ? t("stats.time_published") : t("stats.time_stream")}
              />
              <Groups title={t("stats.best_length")} groups={data.best.length} label={(k) => t(`stats.len.${k}`)} />
              <Groups title={t("stats.best_moment")} groups={data.best.moment} label={(k) => t(`stats.moment.${k}`)} />
            </div>
          )}

          <section className="card" style={{ padding: 20 }} aria-labelledby="data-title">
            <div className="panel-head">
              <h2 className="section-title" id="data-title">
                {t("stats.data")} <span className="count mono">{points.length}</span>
              </h2>
              {points.length > 0 && (
                <button className="btn btn-sm btn-ghost danger-text" onClick={clearAll}>
                  <Icon name="trash" />
                  {t("stats.clear_all")}
                </button>
              )}
            </div>
            {points.length === 0 ? (
              <p className="muted" style={{ margin: 0 }}>
                {t("stats.empty")}
              </p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("stats.col_clip")}</th>
                      <th className="num">{t("stats.real")}</th>
                      <th className="num">{t("stats.likes")}</th>
                      <th className="num">{t("stats.predicted")}</th>
                      <th className="num">{t("publish.viral")}</th>
                      <th>{t("stats.published")}</th>
                      <th aria-label={t("queue.remove")} />
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((p) => (
                      <tr key={p.key}>
                        <td>
                          <a href={href.project(p.project_id)} dir="auto" className="cell-title">
                            {p.title || p.clip_id}
                          </a>
                          <div className="muted cell-sub" dir="auto">
                            {p.project_title}
                          </div>
                        </td>
                        <td className="num mono">{fmtInt(p.views, lang)}</td>
                        <td className="num mono">{p.likes != null ? fmtInt(p.likes, lang) : "–"}</td>
                        <td className="num mono">{p.predicted != null ? fmtInt(p.predicted, lang) : "–"}</td>
                        <td className="num mono">{p.viral_score ?? "–"}</td>
                        <td className="muted">{p.published_at ? relTime(p.published_at) : "–"}</td>
                        <td>
                          <button className="btn btn-sm btn-ghost icon-btn" onClick={() => remove(p.key)} aria-label={t("queue.remove")} title={t("queue.remove")}>
                            <Icon name="x" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
