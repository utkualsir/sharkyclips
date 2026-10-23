import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ApiError,
  urls,
  type Candidate,
  type ClipOptions,
  type Facecam,
  type HypeCurve,
  type Layout,
  type Mode,
  type ProjectDetail,
  type SubtitleStyle,
  type Word,
} from "../api";
import FacecamEditor from "../components/FacecamEditor";
import HypeMap from "../components/HypeMap";
import { Icon } from "../components/Icons";
import { PublishPanel, SignalStats } from "../components/Panels";
import { JobLine, Segmented, Toggle } from "../components/ui";
import VerticalPreview, { resolveLayout } from "../components/VerticalPreview";
import { fmtBytes, fmtTime, sourceLabel } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";

const MODES: Mode[] = ["gaming", "study", "music"];
const SUBS: SubtitleStyle[] = ["bold", "clean", "minimal", "none"];
const LAYOUTS: Layout[] = ["auto", "split", "fit", "crop"];

// ------------------------------------------------------------------ candidate row

function CandidateRow({
  c,
  selected,
  accepted,
  onSelect,
  onAccept,
}: {
  c: Candidate;
  selected: boolean;
  accepted: boolean;
  onSelect: () => void;
  onAccept: (v: boolean) => void;
}) {
  const { t, num } = useI18n();
  const codes = [...new Set(c.reasons.map((r) => r.code))].slice(0, 4);
  const title = c.publish.titles[0] || c.text;
  return (
    <div
      className="cand"
      role="option"
      aria-selected={selected}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect())}
      data-cand={c.id}
    >
      <span className="cand-rank">#{String(c.rank).padStart(2, "0")}</span>
      <div className="cand-body">
        <p className="cand-title" dir="auto">
          {title}
        </p>
        <div className="cand-line">
          <div className="cand-meta">
            <span className="tc">{fmtTime(c.start)}</span>
            <span aria-hidden="true">·</span>
            <span className="tc">{num(Math.round(c.duration))} s</span>
          </div>
          <div className="cand-score" title={`${t("signals.score")}: ${c.hype_score}/100`}>
            <div className="bar">
              <span style={{ width: `${c.hype_score}%` }} />
            </div>
            <span className="n">{num(c.hype_score)}</span>
          </div>
        </div>
        <div className="cand-reasons">
          {codes.map((code) => (
            <span key={code} className="chip">
              {t(`reason.${code}`)}
            </span>
          ))}
        </div>
      </div>
      <div className="cand-accept" onClick={(e) => e.stopPropagation()}>
        <Toggle checked={accepted} onChange={onAccept} label={`${t("cands.accept")} #${c.rank}`} />
        <span className={accepted ? "ok" : ""}>{accepted ? <Icon name="check" size={13} /> : t("cands.accept")}</span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ page

export default function ProjectPage({ id }: { id: string }) {
  const { t, num, relTime } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick, lastFinished } = useJobs();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [curve, setCurve] = useState<HypeCurve | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [words, setWords] = useState<Word[]>([]);
  const [time, setTime] = useState(0);
  const [playingClip, setPlayingClip] = useState(false);
  const [tab, setTab] = useState<"cands" | "clips">("cands");
  const [facecamOpen, setFacecamOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("gaming");
  const video = useRef<HTMLVideoElement>(null);
  const playerBox = useRef<HTMLDivElement>(null);
  const [previewH, setPreviewH] = useState<number | null>(null);
  const saveTimer = useRef<number>();

  const load = useCallback(async () => {
    try {
      const p = await api.project(id);
      setProject(p);
      setMode(p.highlights?.mode ?? p.mode ?? "gaming");
      if (p.highlights) api.hype(id).then(setCurve).catch(() => setCurve(null));
      setSelectedId((cur) =>
        cur && p.highlights?.candidates.some((c) => c.id === cur) ? cur : p.highlights?.candidates[0]?.id ?? null,
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Reload when one of this project's jobs finishes.
  useEffect(() => {
    if (!lastFinished || lastFinished.project_id !== id) return;
    load();
    if (lastFinished.kind === "render" && lastFinished.status === "done") {
      const n = lastFinished.result?.clips?.length ?? 0;
      toast({ kind: "ok", text: t("render.done", { n }), action: { label: t("render.view"), run: () => setTab("clips") } });
      setTab("clips");
    }
    if (lastFinished.status === "error" && lastFinished.error) {
      toast({ kind: "err", text: lastFinished.error.message, hint: lastFinished.error.hint });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedTick]);

  const projectJobs = jobs.filter((j) => j.project_id === id);
  const activeJobs = projectJobs.filter(isActive);
  const renderJob = activeJobs.find((j) => j.kind === "render");
  const pipelineJob = activeJobs.find((j) => j.kind !== "render" && j.kind !== "facecam") ?? null;
  const facecamJob = activeJobs.find((j) => j.kind === "facecam");

  const cands = project?.highlights?.candidates ?? [];
  const selected = cands.find((c) => c.id === selectedId) ?? null;
  const review = project?.review;
  const accepted = useMemo(() => new Set(review?.accepted ?? []), [review]);
  const options: ClipOptions = review?.options ?? { layout: "auto", subtitles: "bold", hook: true };
  const hookText = selected ? review?.hooks[selected.id] ?? selected.default_hook : "";

  // Words of the selected clip (for the live subtitle preview)
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    api.words(id, selected.start, selected.end).then((w) => !cancelled && setWords(w)).catch(() => setWords([]));
    return () => {
      cancelled = true;
    };
  }, [id, selected?.id, selected?.start, selected?.end]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the 9:16 preview as tall as the 16:9 player on wide screens.
  useEffect(() => {
    const el = playerBox.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setPreviewH(window.innerWidth > 720 ? el.clientHeight : null));
    ro.observe(el);
    return () => ro.disconnect();
  }, [project?.highlights]);

  // First frame: jump to the selected clip as soon as the video can seek.
  const didInitialSeek = useRef(false);
  useEffect(() => {
    const v = video.current;
    if (!v || !selected || didInitialSeek.current) return;
    const go = () => {
      if (didInitialSeek.current) return;
      didInitialSeek.current = true;
      v.currentTime = selected.start;
      setTime(selected.start);
    };
    if (v.readyState >= 1) go();
    else v.addEventListener("loadedmetadata", go, { once: true });
    return () => v.removeEventListener("loadedmetadata", go);
  }, [selected, project?.highlights]);

  // Facecam: projects analyzed before this feature existed get a detection run once.
  const askedFacecam = useRef(false);
  useEffect(() => {
    if (!project?.highlights || project.review.facecam_checked || askedFacecam.current) return;
    if (jobs.some((j) => j.project_id === id && isActive(j))) return;
    askedFacecam.current = true;
    api.detectFacecam(id).catch(() => {});
  }, [project, jobs, id]);

  // Player time + stop at the end of the clip when "Play clip" is used.
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    const on = () => {
      setTime(v.currentTime);
      if (playingClip && selected && v.currentTime >= selected.end) {
        v.pause();
        setPlayingClip(false);
      }
    };
    const onPause = () => setPlayingClip(false);
    v.addEventListener("timeupdate", on);
    v.addEventListener("seeked", on);
    v.addEventListener("pause", onPause);
    return () => {
      v.removeEventListener("timeupdate", on);
      v.removeEventListener("seeked", on);
      v.removeEventListener("pause", onPause);
    };
  }, [playingClip, selected, project?.highlights]);

  const seek = (s: number) => {
    const v = video.current;
    if (v) v.currentTime = s;
    setTime(s);
  };

  const select = (c: Candidate, play = false) => {
    setSelectedId(c.id);
    seek(c.start);
    if (play) playClip(c);
    document.querySelector(`[data-cand="${c.id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  const playClip = (c: Candidate | null = selected) => {
    const v = video.current;
    if (!v || !c) return;
    if (v.currentTime < c.start - 0.5 || v.currentTime >= c.end - 0.2) v.currentTime = c.start;
    setPlayingClip(true);
    v.play().catch(() => setPlayingClip(false));
  };

  const step = (dir: 1 | -1) => {
    if (!selected) return;
    const i = cands.findIndex((c) => c.id === selected.id);
    const next = cands[i + dir];
    if (next) select(next);
  };

  // ---------------------------------------------------------------- review updates

  const patchReview = (changes: Partial<NonNullable<typeof review>>, debounce = false) => {
    if (!project) return;
    setProject({ ...project, review: { ...project.review, ...changes } });
    const send = () =>
      api.saveReview(id, changes).catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
    window.clearTimeout(saveTimer.current);
    if (debounce) saveTimer.current = window.setTimeout(send, 600);
    else send();
  };

  const setAccepted = (cid: string, v: boolean) => {
    const next = new Set(accepted);
    if (v) next.add(cid);
    else next.delete(cid);
    // keep rank order
    patchReview({ accepted: cands.filter((c) => next.has(c.id)).map((c) => c.id) });
  };

  const setOption = (o: Partial<ClipOptions>) => patchReview({ options: { ...options, ...o } });

  const setHook = (text: string) => {
    if (!selected || !review) return;
    const hooks = { ...review.hooks };
    if (text.trim() && text !== selected.default_hook) hooks[selected.id] = text;
    else delete hooks[selected.id];
    patchReview({ hooks }, true);
  };

  const saveFacecam = (fc: Facecam | null) => {
    setFacecamOpen(false);
    patchReview({ facecam: fc, facecam_checked: true });
  };

  const render = async () => {
    if (!project || !accepted.size) return;
    window.clearTimeout(saveTimer.current);
    try {
      await api.saveReview(id, { hooks: review!.hooks });
      await api.render(id, [...accepted], options, review!.hooks);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const reanalyze = async () => {
    try {
      await api.highlights(id, mode);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const retry = async () => {
    try {
      if (project?.last_error_kind === "transcribe" || !project?.language) await api.transcribe(id);
      else await api.highlights(id, mode);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  // keyboard: arrows move through candidates, space plays the clip, A toggles accept
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || facecamOpen) return;
      if (e.key === "ArrowDown" || e.key === "j") (e.preventDefault(), step(1));
      else if (e.key === "ArrowUp" || e.key === "k") (e.preventDefault(), step(-1));
      else if (e.key === "a" && selected) setAccepted(selected.id, !accepted.has(selected.id));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  // ---------------------------------------------------------------- render

  if (notFound) {
    return (
      <main className="page">
        <a className="crumbs" href={href.library}>
          <Icon name="chevron-left" className="icon flip-rtl" />
          {t("nav.library")}
        </a>
        <div className="empty">
          <h1 className="display">{t("project.not_found")}</h1>
        </div>
      </main>
    );
  }
  if (!project) {
    return (
      <main className="page">
        <div className="skeleton" style={{ height: 40, width: 380, marginBottom: 24 }} />
        <div className="proj-layout">
          <div className="skeleton" style={{ aspectRatio: "16/9", borderRadius: 14 }} />
          <div className="skeleton" style={{ height: 480, borderRadius: 16 }} />
        </div>
      </main>
    );
  }

  const langName = UI_LANGUAGES.find((l) => l.code === project.language)?.name ?? project.language;
  const clips = Object.values(project.clips).sort((a, b) => a.rank - b.rank);
  const fc = review?.facecam ?? null;
  const src = project.source.type === "file" ? t("library.source_file") : sourceLabel(project.source.value);

  return (
    <main className="page">
      <div className="proj-head">
        <div style={{ minWidth: 0 }}>
          <a className="crumbs" href={href.library}>
            <Icon name="chevron-left" className="icon flip-rtl" />
            {t("nav.library")}
          </a>
          <h1 className="display" dir="auto">
            {project.title}
          </h1>
          <div className="meta-row">
            {project.mode && <span className="chip">{t(`mode.${project.mode}`)}</span>}
            {project.duration != null && <span className="chip chip-outline tc">{fmtTime(project.duration)}</span>}
            {langName && (
              <span className="chip chip-outline">
                <Icon name="globe" size={12} />
                {langName}
              </span>
            )}
            {project.resolution && <span className="chip chip-outline mono">{project.resolution}</span>}
            {src &&
              (project.source.type === "url" && project.source.value ? (
                <a className="chip chip-outline" href={project.source.value} target="_blank" rel="noreferrer">
                  <Icon name="link" size={12} />
                  {src}
                </a>
              ) : (
                <span className="chip chip-outline">
                  <Icon name="file" size={12} />
                  {src}
                </span>
              ))}
          </div>
        </div>
        {project.language && (
          <div className="proj-actions">
            <select
              className="select select-sm"
              style={{ width: "auto" }}
              value={mode}
              onChange={(e) => setMode(e.target.value as Mode)}
              aria-label={t("new.mode")}
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {t(`mode.${m}`)}
                </option>
              ))}
            </select>
            <button className="btn btn-sm" onClick={reanalyze} disabled={!!pipelineJob}>
              <Icon name="refresh" />
              {project.highlights ? t("project.reanalyze") : t("project.analyze")}
            </button>
          </div>
        )}
      </div>

      {pipelineJob && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <JobLine job={pipelineJob} onCancel={() => api.cancelJob(pipelineJob.id)} />
        </div>
      )}

      {project.state === "error" && project.last_error && !pipelineJob && (
        <div className="notice notice-danger" style={{ marginBottom: 16 }}>
          <Icon name="alert" />
          <div style={{ flex: 1 }}>
            <div className="notice-title">{t("project.error_title")}</div>
            <div>{project.last_error.message}</div>
            {project.last_error.hint && <div className="muted">{project.last_error.hint}</div>}
          </div>
          <button className="btn btn-sm" onClick={retry}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {!project.highlights ? (
        <div className="empty">
          {pipelineJob ? <span className="spinner" style={{ width: 28, height: 28 }} /> : <Icon name="sparkles" size={28} />}
          <h2 className="display">{pipelineJob ? t("project.processing_title") : t("project.no_highlights_title")}</h2>
          <p style={{ margin: 0, maxWidth: "48ch" }}>
            {pipelineJob ? t("project.processing_body") : t("project.no_highlights_body")}
          </p>
          {!pipelineJob && (
            <button className="btn btn-primary" onClick={project.language ? reanalyze : retry}>
              {project.language ? t("project.analyze") : t("project.transcribe")}
            </button>
          )}
        </div>
      ) : (
        <div className="proj-layout">
          <div className="proj-main">
            <section className="panel">
              <div className="stage">
                <div className="stage-left">
                  <div className="player" ref={playerBox}>
                    {project.playable ? (
                      <video ref={video} src={urls.source(id)} controls playsInline preload="metadata" />
                    ) : (
                      <div style={{ display: "grid", placeItems: "center", height: "100%", color: "#aeb7ca" }}>
                        <span className="spinner" />
                      </div>
                    )}
                  </div>
                </div>
                <div className="stage-right">
                  <div className="vprev">
                    <div
                      className="vprev-frame"
                      style={previewH ? { height: previewH, width: (previewH * 9) / 16 } : undefined}
                    >
                      <VerticalPreview
                        video={video}
                        clip={selected}
                        options={options}
                        facecam={fc}
                        words={words}
                        lang={project.language}
                        hookText={hookText}
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="player-bar">
                <button className="btn btn-sm icon-btn" onClick={() => step(-1)} aria-label={t("player.prev")} title={t("player.prev")}>
                  <Icon name="chevron-left" className="icon flip-rtl" />
                </button>
                {playingClip ? (
                  <button className="btn btn-sm" onClick={() => video.current?.pause()}>
                    <Icon name="pause" />
                    {t("player.stop")}
                  </button>
                ) : (
                  <button className="btn btn-sm btn-primary" onClick={() => playClip()} disabled={!selected}>
                    <Icon name="play" />
                    {t("player.play_clip")}
                  </button>
                )}
                <button className="btn btn-sm icon-btn" onClick={() => step(1)} aria-label={t("player.next")} title={t("player.next")}>
                  <Icon name="chevron-right" className="icon flip-rtl" />
                </button>
                {selected && (
                  <span className="tc" style={{ marginInlineStart: 4 }}>
                    #{String(selected.rank).padStart(2, "0")} · {fmtTime(selected.start)} – {fmtTime(selected.end)}
                  </span>
                )}
                <span style={{ flex: 1 }} />
                <span className="tc">
                  {fmtTime(time, true)} / {fmtTime(project.duration)}
                </span>
                <span className="chip chip-outline">{t("preview.title")}</span>
              </div>
            </section>

            {curve && (
              <section className="panel" aria-labelledby="hype-title">
                <div className="panel-head">
                  <h2 className="section-title" id="hype-title">
                    {t("hype.title")}
                  </h2>
                  <div className="legend">
                    <span>
                      <i style={{ background: "var(--gold)" }} />
                      {t("hype.selected")}
                    </span>
                    <span>
                      <i style={{ background: "var(--bar-cand)" }} />
                      {t("hype.candidates")}
                    </span>
                    <span>
                      <i style={{ background: "var(--bar)" }} />
                      {t("hype.curve")}
                    </span>
                  </div>
                </div>
                <HypeMap
                  curve={curve}
                  candidates={cands}
                  selected={selected}
                  currentTime={time}
                  onSeek={(s, c) => {
                    if (c && c.id !== selectedId) setSelectedId(c.id);
                    seek(s);
                  }}
                />
              </section>
            )}

            <div className="lower-grid">
              <SignalStats cand={selected} project={project} />
              <PublishPanel cand={selected} projectId={id} />
            </div>
          </div>

          <aside className="card proj-side">
            <div className="side-tabs" role="tablist">
              <button role="tab" aria-selected={tab === "cands"} onClick={() => setTab("cands")}>
                {t("cands.tab")} <span className="count mono">{cands.length}</span>
              </button>
              <button role="tab" aria-selected={tab === "clips"} onClick={() => setTab("clips")}>
                {t("clips.tab")} <span className="count mono">{clips.length}</span>
              </button>
              <span style={{ flex: 1 }} />
              {tab === "cands" && accepted.size > 0 && (
                <span className="chip chip-success" style={{ alignSelf: "center" }}>
                  {t("cands.accepted", { n: accepted.size })}
                </span>
              )}
            </div>

            {tab === "cands" ? (
              <>
                <div className="side-scroll" role="listbox" aria-label={t("cands.tab")}>
                  {cands.map((c) => (
                    <CandidateRow
                      key={c.id}
                      c={c}
                      selected={c.id === selectedId}
                      accepted={accepted.has(c.id)}
                      onSelect={() => select(c)}
                      onAccept={(v) => setAccepted(c.id, v)}
                    />
                  ))}
                </div>
                <div className="render-panel">
                  <div className="render-row">
                    <label>{t("render.subtitles")}</label>
                    <Segmented
                      value={options.subtitles}
                      options={SUBS.map((s) => ({ value: s, label: t(`sub.${s}`) }))}
                      onChange={(s) => setOption({ subtitles: s })}
                      label={t("render.subtitles")}
                    />
                  </div>
                  <div className="render-row">
                    <label htmlFor="layout-sel">{t("render.layout")}</label>
                    <select
                      id="layout-sel"
                      className="select select-sm"
                      value={options.layout}
                      onChange={(e) => setOption({ layout: e.target.value as Layout })}
                    >
                      {LAYOUTS.map((l) => (
                        <option key={l} value={l}>
                          {l === "auto" ? `${t("layout.auto")} (${t(`layout.${resolveLayout("auto", fc)}`)})` : t(`layout.${l}`)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="render-row">
                    <label>{t("render.hook")}</label>
                    <div className="hook-row">
                      <Toggle checked={options.hook} onChange={(v) => setOption({ hook: v })} label={t("render.hook")} />
                      <input
                        className="input"
                        style={{ height: 32, fontSize: 13 }}
                        dir="auto"
                        disabled={!options.hook || !selected}
                        value={hookText}
                        maxLength={120}
                        placeholder={t("render.hook_placeholder")}
                        onChange={(e) => setHook(e.target.value)}
                        aria-label={t("render.hook_placeholder")}
                      />
                    </div>
                  </div>
                  <div className="facecam-line">
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Icon name="camera" size={14} />
                      {t("facecam.label")}:{" "}
                      {facecamJob ? (
                        <>
                          <span className="spinner" style={{ width: 12, height: 12 }} /> {t("facecam.detecting")}
                        </>
                      ) : fc ? (
                        <span className="gold">{fc.source === "manual" ? t("facecam.manual") : t("facecam.detected")}</span>
                      ) : (
                        t("facecam.none")
                      )}
                    </span>
                    <button className="btn btn-sm btn-ghost" onClick={() => setFacecamOpen(true)} disabled={!!facecamJob}>
                      <Icon name="scan" />
                      {t("common.edit")}
                    </button>
                  </div>
                  {renderJob ? (
                    <JobLine job={renderJob} onCancel={() => api.cancelJob(renderJob.id)} />
                  ) : (
                    <button className="btn btn-primary btn-lg btn-block" disabled={!accepted.size} onClick={render}>
                      <Icon name="film" />
                      {accepted.size ? t("render.button", { n: accepted.size }) : t("render.none")}
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="side-scroll">
                {clips.length === 0 ? (
                  <p className="muted" style={{ padding: 16 }}>
                    {t("clips.empty")}
                  </p>
                ) : (
                  <div className="clips-grid">
                    {clips.map((c) => (
                      <div className="clip-card" key={c.id}>
                        <video src={urls.clip(id, c.id, c.rendered_at)} controls playsInline preload="metadata" />
                        <div className="foot">
                          <div style={{ display: "grid", minWidth: 0 }}>
                            <span className="tc">
                              #{String(c.rank).padStart(2, "0")} · {num(Math.round(c.duration))} s
                            </span>
                            <span className="muted" style={{ fontSize: 11 }} title={`${c.encoder} · ${fmtBytes(c.size_bytes)}`}>
                              {t("clips.rendered", { when: relTime(c.rendered_at) })}
                            </span>
                          </div>
                          <a
                            className="btn btn-sm icon-btn"
                            href={urls.clipDownload(id, c.id)}
                            download
                            aria-label={t("common.download")}
                            title={`${t("common.download")} · ${fmtBytes(c.size_bytes)}`}
                          >
                            <Icon name="download" />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      )}

      {facecamOpen && (
        <FacecamEditor
          projectId={id}
          time={selected?.peak ?? (project.duration ?? 0) / 2}
          initial={fc}
          onClose={() => setFacecamOpen(false)}
          onSave={saveFacecam}
          onDetect={() => {
            setFacecamOpen(false);
            api.detectFacecam(id).catch((e) => toast({ kind: "err", text: e.message }));
          }}
        />
      )}
    </main>
  );
}
