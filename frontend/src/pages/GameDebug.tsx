import { useCallback, useEffect, useMemo, useState } from "react";
import { api, urls, type GameChoice, type GameEvent, type GameId, type GameProbe, type GameView } from "../api";
import { Icon } from "../components/Icons";
import { JobLine } from "../components/ui";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";

type Box = [number, number, number, number];

// Events too small to matter when calibrating (shown again with the toggle).
const SMALL = new Set(["lol_assist", "df_assist", "df_revive"]);

/** "Multikill ×3", "Quadra kill · Yasuo" */
export function gameReasonLabel(t: (k: string) => string, code: string, value?: string | null): string {
  const base = t(`reason.${code}`);
  if (!value) return base;
  if (code === "df_multikill") return `${base} ×${value}`;
  if (code.startsWith("lol_")) return `${base} · ${value}`;
  return base;
}

export function whyText(t: (k: string, v?: Record<string, string | number>) => string, why: string, detected: string | null) {
  const [kind, ...rest] = (why || "").split(":");
  if (!detected) return t("game.why_none");
  if (kind === "title") return t("game.why_title");
  return t("game.why_transcript", { detail: rest.join(":").trim() });
}

function RegionOverlay({
  regions,
  selected,
  base,
  onSelect,
}: {
  regions: Record<string, { box: Box; label: string }>;
  selected: string | null;
  base: [number, number];
  onSelect: (name: string) => void;
}) {
  return (
    <svg className="gd-overlay" viewBox={`0 0 ${base[0]} ${base[1]}`} preserveAspectRatio="none" aria-hidden="true">
      {Object.entries(regions).map(([name, r]) => {
        const [x, y, w, h] = r.box;
        const on = name === selected;
        return (
          <g key={name} className={`gd-box${on ? " on" : ""}`} onClick={() => onSelect(name)}>
            <rect x={x} y={y} width={w} height={h} vectorEffect="non-scaling-stroke" />
            <text x={x + 4} y={y > 34 ? y - 8 : y + h + 26}>
              {r.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function GameDebug({ id }: { id: string }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs, lastFinished, finishedTick } = useJobs();
  const [view, setView] = useState<GameView | null>(null);
  const [title, setTitle] = useState("");
  const [time, setTime] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, Box>>({});
  const [probe, setProbe] = useState<GameProbe | null>(null);
  const [probing, setProbing] = useState(false);
  const [hideSmall, setHideSmall] = useState(true);

  const load = useCallback(async () => {
    const v = await api.game(id, true);
    setView(v);
    setDraft(Object.fromEntries(Object.entries(v.regions).map(([k, r]) => [k, r.box])));
    return v;
  }, [id]);

  useEffect(() => {
    api.project(id).then((p) => setTitle(p.title)).catch(() => {});
    load().then((v) => {
      const first = v.events.find((e) => !SMALL.has(e.code));
      if (first) setTime(Math.max(0, first.t));
    });
  }, [id, load]);

  useEffect(() => {
    if (lastFinished?.project_id === id && lastFinished.kind === "highlights") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedTick]);

  const pipelineJob = jobs.find((j) => j.project_id === id && j.kind === "highlights" && isActive(j));
  const regionLabel = (k: string) => {
    const s = t(`game.region.${k}`);
    return s === `game.region.${k}` ? view?.regions[k]?.label ?? k : s;
  };
  const events = useMemo(
    () => (view?.events ?? []).filter((e) => !hideSmall || !SMALL.has(e.code)),
    [view, hideSmall],
  );
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of view?.events ?? []) m.set(e.code, (m.get(e.code) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [view]);
  const reads = useMemo(
    () => (view?.reads ?? []).filter((r) => Math.abs(r.t - time) <= 2.5 && r.text.trim()),
    [view, time],
  );

  if (!view) {
    return (
      <main className="page">
        <div className="skeleton" style={{ height: 40, width: 380, marginBottom: 24 }} />
        <div className="skeleton" style={{ height: 420, borderRadius: 16 }} />
      </main>
    );
  }

  const gid: GameId | null = view.game ?? view.scan?.game ?? null;
  const overlay = Object.fromEntries(
    Object.entries(view.regions).map(([k, r]) => [k, { box: draft[k] ?? r.box, label: regionLabel(k) }]),
  );

  const choose = async (choice: GameChoice) => {
    try {
      await api.setGame(id, choice);
      await load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const rescan = async () => {
    try {
      await api.rescanGame(id);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const readFrame = async () => {
    if (!gid) return;
    setProbing(true);
    try {
      setProbe(await api.probeGame(id, time, gid));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setProbing(false);
    }
  };

  const saveRegion = async (name: string, reset = false) => {
    if (!gid) return;
    try {
      await api.saveGameRegion(gid, name, reset ? null : draft[name]);
      await load();
      toast({ kind: "ok", text: t("game.saved") });
      setProbe(null);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const setBox = (name: string, i: number, v: number) => {
    const b = [...(draft[name] ?? view.regions[name].box)] as Box;
    b[i] = Math.round(v) || 0;
    setDraft({ ...draft, [name]: b });
  };

  const jump = (dir: 1 | -1) => {
    const list = dir > 0 ? events : [...events].reverse();
    const next = list.find((e) => (dir > 0 ? e.t > time + 0.4 : e.t < time - 0.4));
    if (next) setTime(next.t);
  };

  const pick = (e: GameEvent) => {
    setTime(e.t);
    setProbe(null);
  };

  const stats = view.scan?.stats;

  return (
    <main className="page game-page">
      <a className="crumbs" href={href.project(id)}>
        <Icon name="chevron-left" className="icon flip-rtl" />
        <span dir="auto">{title}</span>
      </a>
      <div className="page-head">
        <div>
          <h1 className="display">{t("game.title")}</h1>
          <p className="lede">{t("game.lede")}</p>
        </div>
      </div>

      <section className="card gd-head">
        <div className="gd-pick">
          <label className="field-label" htmlFor="gd-game">
            {t("game.label")}
          </label>
          <select id="gd-game" className="select" value={view.choice} onChange={(e) => choose(e.target.value as GameChoice)}>
            {view.choices.map((c) => (
              <option key={c} value={c}>
                {c === "auto"
                  ? view.detected
                    ? t("game.auto_detected", { name: view.games[view.detected] })
                    : t("game.auto_none")
                  : c === "other"
                    ? t("game.other")
                    : view.games[c as GameId]}
              </option>
            ))}
          </select>
          <span className="muted gd-why">{whyText(t, view.why, view.detected)}</span>
        </div>
        <div className="gd-status">
          {view.scan?.champion && (
            <span className="chip chip-gold">{t("game.champion", { name: view.scan.champion.name })}</span>
          )}
          {stats && (
            <span className="muted mono gd-stats">
              {t("game.scan_stats", {
                frames: num(stats.frames),
                speed: num(stats.speed),
                ocr: num(stats.ocr_calls),
                decoder: stats.decoder === "nvdec" ? "NVDEC" : "CPU",
              })}
            </span>
          )}
          {gid && (
            <button className="btn btn-sm" onClick={rescan} disabled={!!pipelineJob}>
              <Icon name="scan" />
              {t("game.rescan")}
            </button>
          )}
        </div>
        {pipelineJob && <JobLine job={pipelineJob} />}
        {!gid && <p className="muted">{t("game.no_preset")}</p>}
        {gid && !view.scan && !pipelineJob && <p className="muted">{t("game.not_scanned")}</p>}
        {view.scan && !view.scan.current && <p className="gd-warn">{t("game.stale")}</p>}
      </section>

      {gid && (
        <div className="gd-layout">
          <section className="card gd-frame-card" aria-labelledby="gd-frame">
            <div className="q-section-head">
              <h2 className="section-title" id="gd-frame">
                {t("game.frame")} <span className="mono muted">{fmtTime(time)}</span>
              </h2>
              <div className="gd-nav">
                <button className="btn btn-sm btn-ghost icon-btn" onClick={() => jump(-1)} aria-label={t("game.prev_event")} title={t("game.prev_event")}>
                  <Icon name="chevron-left" className="icon flip-rtl" />
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => setTime(Math.max(0, time - 0.5))}>
                  −0.5 s
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => setTime(time + 0.5)}>
                  +0.5 s
                </button>
                <button className="btn btn-sm btn-ghost icon-btn" onClick={() => jump(1)} aria-label={t("game.next_event")} title={t("game.next_event")}>
                  <Icon name="chevron-right" className="icon flip-rtl" />
                </button>
                <button className="btn btn-sm" onClick={readFrame} disabled={probing}>
                  <Icon name="eye" />
                  {t("game.read_frame")}
                </button>
              </div>
            </div>
            <div className="gd-frame">
              <img src={urls.frame(id, time, 1280)} alt="" />
              <RegionOverlay regions={overlay} selected={selected} base={view.base_size} onSelect={setSelected} />
            </div>
            {probe && (
              <ul className="gd-probe">
                {Object.entries(probe.regions).map(([name, r]) => (
                  <li key={name}>
                    <span className="field-label">{regionLabel(name)}</span>
                    <span className="mono" dir="auto">
                      {r.text || <span className="muted">{t("game.no_text")}</span>}
                    </span>
                    {r.events.map((c) => (
                      <span key={c} className="chip chip-game">
                        {t(`reason.${c}`)}
                      </span>
                    ))}
                  </li>
                ))}
              </ul>
            )}
            <div className="gd-reads">
              <h3 className="field-label">{t("game.reads")}</h3>
              {reads.length === 0 ? (
                <p className="muted">{t("game.no_reads")}</p>
              ) : (
                <ul>
                  {reads.slice(0, 14).map((r, i) => (
                    <li key={i}>
                      <span className="mono muted">{fmtTime(r.t)}</span>
                      <span className="chip chip-outline">{regionLabel(r.region)}</span>
                      <span className="mono" dir="auto">
                        {r.text}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <div className="gd-side">
            <section className="card" aria-labelledby="gd-events">
              <div className="q-section-head">
                <h2 className="section-title" id="gd-events">
                  {t("game.events")} <span className="count mono">{view.events.length}</span>
                </h2>
                <label className="gd-check">
                  <input type="checkbox" checked={hideSmall} onChange={(e) => setHideSmall(e.target.checked)} />
                  {t("game.hide_small")}
                </label>
              </div>
              {counts.length > 0 && (
                <div className="cand-reasons gd-counts">
                  {counts.map(([code, n]) => (
                    <span key={code} className="chip">
                      {t(`reason.${code}`)} <span className="mono">{num(n)}</span>
                    </span>
                  ))}
                </div>
              )}
              {events.length === 0 ? (
                <p className="muted">{t("game.no_events")}</p>
              ) : (
                <ol className="gd-events">
                  {events.map((e, i) => (
                    <li key={i}>
                      <button
                        className={`gd-event${Math.abs(e.t - time) < 0.3 ? " on" : ""}`}
                        onClick={() => pick(e)}
                      >
                        <span className="mono">{fmtTime(e.t)}</span>
                        <span className={`chip${e.strength >= 0.5 ? " chip-game" : ""}`}>
                          {gameReasonLabel(t, e.code, e.code === "df_multikill" ? e.value : e.champion)}
                        </span>
                        <span className="muted gd-src">{e.source.split("+").map((s) => t(`game.src.${s}`)).join(" + ")}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section className="card" aria-labelledby="gd-regions">
              <h2 className="section-title" id="gd-regions">
                {t("game.regions")}
              </h2>
              <p className="muted gd-note">{t("game.regions_note")}</p>
              <div className="gd-regions">
                {Object.entries(view.regions).map(([name, r]) => {
                  const b = draft[name] ?? r.box;
                  const dirty = b.some((v, i) => v !== r.box[i]);
                  return (
                    <div
                      key={name}
                      className={`gd-region${selected === name ? " on" : ""}`}
                      onFocus={() => setSelected(name)}
                      onMouseEnter={() => setSelected(name)}
                    >
                      <div className="gd-region-head">
                        <strong>{regionLabel(name)}</strong>
                        {r.custom && <span className="chip chip-outline">{t("game.custom")}</span>}
                      </div>
                      <div className="gd-region-inputs">
                        {(["x", "y", "w", "h"] as const).map((k, i) => (
                          <label key={k}>
                            <span className="mono muted">{k}</span>
                            <input
                              className="input mono"
                              type="number"
                              value={b[i]}
                              min={0}
                              max={i % 2 === 0 ? 1920 : 1080}
                              onChange={(e) => setBox(name, i, Number(e.target.value))}
                            />
                          </label>
                        ))}
                      </div>
                      <div className="gd-region-actions">
                        <button className="btn btn-sm" disabled={!dirty} onClick={() => saveRegion(name)}>
                          {t("game.save")}
                        </button>
                        {r.custom && (
                          <button className="btn btn-sm btn-ghost" onClick={() => saveRegion(name, true)}>
                            {t("game.reset")}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="card" aria-labelledby="gd-sounds">
              <h2 className="section-title" id="gd-sounds">
                {t("game.sounds")}
              </h2>
              <p className="muted gd-note">{t("game.sounds_note")}</p>
              {view.sounds.folder && <p className="mono gd-path">{view.sounds.folder}</p>}
              {view.sounds.clips?.length ? (
                <div className="cand-reasons">
                  {view.sounds.clips.map((c) => (
                    <span key={c} className="chip mono">
                      {c}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted">{t("game.sounds_none")}</p>
              )}
              {!!view.sounds.ignored?.length && (
                <p className="gd-warn">{t("game.sounds_ignored", { files: view.sounds.ignored.join(", ") })}</p>
              )}
            </section>
          </div>
        </div>
      )}
    </main>
  );
}
