import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ApiError,
  urls,
  type BrandState,
  type Candidate,
  type ClipEdit,
  type MusicTrack,
  type ClipExport,
  type ClipOptions,
  type Facecam,
  type GameChoice,
  type GameId,
  type HookTests,
  type HypeCurve,
  type Layout,
  type Mode,
  type ProjectDetail,
  type RenderedClip,
  type SubtitleStyle,
  type Word,
  type YoutubeUpload,
} from "../api";
import EditTools from "../components/EditTools";
import FastReview, { ShortcutSheet } from "../components/FastReview";
import { ExportDialog, ExportsList, UploadDialog, UploadsLine } from "../components/Publish";
import { PublishSetupDialog } from "../components/PublishTools";
import TranscriptEditor from "../components/TranscriptEditor";
import SwearReview from "../components/SwearReview";
import VoicesPanel from "../components/VoicesPanel";
import FacecamEditor from "../components/FacecamEditor";
import HypeMap from "../components/HypeMap";
import { Icon } from "../components/Icons";
import { fmtRatio, PublishPanel, SignalStats } from "../components/Panels";
import { JobLine, Segmented, Toggle } from "../components/ui";
import VerticalPreview, { resolveLayout } from "../components/VerticalPreview";
import { fmtBytes, fmtCompact, fmtTime, sourceLabel } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useMeta } from "../meta";
import { CountUp } from "../motion";
import { href } from "../router";
import { useToast } from "../toast";
import { effectiveRange, maskWord, renderRange, typing, useHistory, usePlan, usePreviewPlayback } from "../editing";
import HookTestDialog from "../components/HookTest";
import { gameReasonLabel, whyText } from "./GameDebug";

const MODES: Mode[] = ["gaming", "study", "music"];
const GAME_NAMES: Record<GameId, string> = { delta_force: "Delta Force", lol: "League of Legends" };
const GAME_CODE = /^(lol|df)_/;
const SUBS: SubtitleStyle[] = ["bold", "karaoke", "speakers", "clean", "minimal", "none"];
const LAYOUTS: Layout[] = ["auto", "split", "fit", "crop"];
type HookMode = "off" | "text" | "flash" | "both";
const HOOK_MODES: HookMode[] = ["off", "text", "flash", "both"];
type Snapshot = { accepted: string[]; rejected: string[]; edits: Record<string, ClipEdit> };

// ------------------------------------------------------------------ candidate row

function CandidateRow({
  c,
  selected,
  accepted,
  rejected,
  edited,
  onSelect,
  onAccept,
  onDelete,
}: {
  c: Candidate;
  selected: boolean;
  accepted: boolean;
  rejected: boolean;
  edited: boolean;
  onSelect: () => void;
  onAccept: (v: boolean) => void;
  onDelete?: () => void;
}) {
  const { t, num } = useI18n();
  const codes = [...new Set(c.reasons.map((r) => r.code))].slice(0, 4);
  const valueOf = (code: string) => c.reasons.find((r) => r.code === code && r.value)?.value;
  const title = c.publish.titles[0] || c.text;
  const cal = c.publish.calibrated ?? null;
  const viral = c.publish.available && c.publish.viral_score != null ? cal?.score ?? c.publish.viral_score : null;
  const label = c.publish.viral_label;
  const chatSpike = c.reasons
    .filter((r) => r.code === "chat_spike" && r.value)
    .sort((a, b) => b.strength - a.strength)[0]?.value;
  return (
    <div
      className={`cand${rejected ? " rejected" : ""}`}
      role="listitem"
      aria-current={selected ? "true" : undefined}
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
        {viral != null && (
          <div
            className="cand-viral"
            title={
              cal
                ? t("cal.tooltip", { score: cal.score, def: cal.default, n: cal.n })
                : `${t("publish.viral")}: ${viral}/100`
            }
          >
            <span className="v-num">
              <Icon name="sparkles" size={12} />
              <CountUp value={viral} format={num} />
              <span className="v-den">/100</span>
            </span>
            {label && !cal && <span className={`v-pill v-${label}`}>{t(`publish.label.${label}`)}</span>}
            {cal && <span className="v-pill v-cal">{t("cal.badge")}</span>}
          </div>
        )}
        <div className="cand-line">
          <div className="cand-meta">
            <span className="tc">{fmtTime(c.start)}</span>
            <span aria-hidden="true">·</span>
            <span className="tc">{num(Math.round(c.duration))} s</span>
            {edited && (
              <span className="cand-flag" title={t("tx.edited")}>
                <Icon name="wand" size={11} />
              </span>
            )}
          </div>
          <div className={`cand-score${viral != null ? " secondary" : ""}`} title={`${t("signals.score")}: ${c.hype_score}/100`}>
            <span className="lbl">{t("cands.hype_short")}</span>
            <div className="bar">
              <span style={{ width: `${c.hype_score}%` }} />
            </div>
            <span className="n"><CountUp value={c.hype_score} format={num} /></span>
          </div>
        </div>
        <div className="cand-reasons">
          {rejected && <span className="chip chip-danger">{t("fast.skipped")}</span>}
          {codes.map((code) => (
            <span
              key={code}
              className={`chip${code === "chat_spike" ? " chip-gold" : ""}${GAME_CODE.test(code) ? " chip-game" : ""}`}
            >
              {GAME_CODE.test(code) ? gameReasonLabel(t, code, code === "df_multikill" ? valueOf(code) : null) : t(`reason.${code}`)}
              {code === "chat_spike" && chatSpike && <span className="mono"> {fmtRatio(chatSpike, num)}</span>}
            </span>
          ))}
        </div>
      </div>
      <div className="cand-accept" onClick={(e) => e.stopPropagation()}>
        <Toggle checked={accepted} onChange={onAccept} label={`${t("cands.accept")} #${c.rank}`} />
        <span className={accepted ? "ok" : ""}>{accepted ? <Icon name="check" size={13} /> : t("cands.accept")}</span>
        {onDelete && (
          <button className="btn btn-sm btn-ghost icon-btn" onClick={onDelete} aria-label={t("manual.delete")} title={t("manual.delete")}>
            <Icon name="trash" size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ real views (calibration)

function PerformanceForm({ projectId, clip, onSaved }: { projectId: string; clip: RenderedClip; onSaved: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const perf = clip.performance ?? null;
  const [open, setOpen] = useState(false);
  const [views, setViews] = useState("");
  const [likes, setLikes] = useState("");
  const [published, setPublished] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setViews(perf ? String(perf.views) : "");
    setLikes(perf?.likes != null ? String(perf.likes) : "");
    setPublished(perf?.published_at?.slice(0, 16) ?? "");
  }, [perf?.views, perf?.likes, perf?.published_at, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const digits = (v: string) => v.replace(/[^0-9]/g, "");
  const save = async () => {
    if (!digits(views)) return;
    setBusy(true);
    try {
      const r = await api.setPerformance(projectId, clip.id, {
        views: Number(digits(views)),
        likes: digits(likes) ? Number(digits(likes)) : null,
        published_at: published || null,
      });
      const st = r.calibration;
      toast({
        kind: "ok",
        text: st.calibrated
          ? t("cal.saved_calibrated", { n: st.model_points })
          : t("cal.saved_progress", { n: st.n, need: st.needed }),
      });
      setOpen(false);
      onSaved();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api.deletePerformance(projectId, clip.id);
      setOpen(false);
      onSaved();
    } catch (e: any) {
      toast({ kind: "err", text: e.message });
    }
    setBusy(false);
  };

  if (!open) {
    return (
      <button className={`perf-line${perf ? " has" : ""}`} onClick={() => setOpen(true)} data-perf={clip.id}>
        <Icon name="eye" size={13} />
        {perf ? (
          <span>
            <b className="mono">{fmtCompact(perf.views, lang)}</b> {t("cal.views")}
            {perf.likes != null && (
              <>
                {" · "}
                <b className="mono">{fmtCompact(perf.likes, lang)}</b> {t("cal.likes")}
              </>
            )}
          </span>
        ) : (
          <span>{t("cal.add_views")}</span>
        )}
      </button>
    );
  }
  return (
    <form
      className="perf-form"
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <label>
        <span>{t("cal.views_label")}</span>
        <input
          className="input"
          inputMode="numeric"
          autoFocus
          value={views}
          onChange={(e) => setViews(e.target.value)}
          placeholder="12500"
          name="views"
        />
      </label>
      <label>
        <span>{t("cal.likes_label")}</span>
        <input
          className="input"
          inputMode="numeric"
          value={likes}
          onChange={(e) => setLikes(e.target.value)}
          placeholder={t("cal.optional")}
          name="likes"
        />
      </label>
      <label>
        <span>{t("cal.published_label")}</span>
        <input className="input" type="datetime-local" value={published} onChange={(e) => setPublished(e.target.value)} />
      </label>
      <div className="perf-actions">
        {perf && (
          <button type="button" className="btn btn-sm btn-ghost danger-text" onClick={remove} disabled={busy}>
            {t("cal.remove")}
          </button>
        )}
        <span style={{ flex: 1 }} />
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </button>
        <button type="submit" className="btn btn-sm btn-primary" disabled={busy || !digits(views)}>
          {t("common.save")}
        </button>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ page

export default function ProjectPage({ id }: { id: string }) {
  const { t, num, relTime } = useI18n();
  const meta = useMeta();
  const chatInput = useRef<HTMLInputElement>(null);
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
  const [outLang, setOutLang] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const playerBox = useRef<HTMLDivElement>(null);
  const [previewH, setPreviewH] = useState<number | null>(null);
  const saveTimer = useRef<number>();
  const [exportIds, setExportIds] = useState<string[] | null>(null);
  const [uploadFor, setUploadFor] = useState<{ cid: string; source?: string } | null>(null);
  const [publishFor, setPublishFor] = useState<string | null>(null);
  const [clipExports, setClipExports] = useState<ClipExport[]>([]);
  const [uploads, setUploads] = useState<Record<string, YoutubeUpload[]>>({});
  const [marks, setMarks] = useState<{ in: number | null; out: number | null }>({ in: null, out: null });
  const [fastOpen, setFastOpen] = useState(false);
  const [keysOpen, setKeysOpen] = useState(false);
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [brand, setBrand] = useState<BrandState | null>(null);
  const [loopPlay, setLoopPlay] = useState(false);
  const [hookTests, setHookTests] = useState<HookTests | null>(null);
  const [hookFor, setHookFor] = useState<string | null>(null);
  const history = useHistory<Snapshot>();
  useEffect(() => {
    api.music().then((m) => setTracks(m.tracks)).catch(() => {});
    api.brand().then(setBrand).catch(() => {});
  }, []);
  const loadExports = useCallback(() => {
    api.clipExports(id).then(setClipExports).catch(() => {});
    api.uploads(id).then(setUploads).catch(() => {});
    api.hookTests(id).then(setHookTests).catch(() => {});
  }, [id]);

  const load = useCallback(async () => {
    try {
      const p = await api.project(id);
      setProject(p);
      setMode(p.highlights?.mode ?? p.mode ?? "gaming");
      setOutLang((cur) => cur ?? p.output_language);
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
    loadExports();
  }, [load, loadExports]);

  // Reload when one of this project's jobs finishes.
  useEffect(() => {
    if (!lastFinished || lastFinished.project_id !== id) return;
    load();
    if (["export", "upload", "render", "ab"].includes(lastFinished.kind)) loadExports();
    if (lastFinished.kind === "ab" && lastFinished.status === "done" && lastFinished.result?.clip_id) {
      const cid = lastFinished.result.clip_id as string;
      toast({ kind: "ok", text: t("ab.done", { label: lastFinished.result.winner }), action: { label: t("ab.open"), run: () => setHookFor(cid) } });
    }
    const stillExporting = jobs.some((j) => j.kind === "export" && j.project_id === id && isActive(j));
    if (lastFinished.kind === "export" && lastFinished.status === "done" && !stillExporting) {
      toast({ kind: "ok", text: t("export.done"), action: { label: t("render.view"), run: () => setTab("clips") } });
      setTab("clips");
    }
    if (lastFinished.kind === "upload" && lastFinished.status === "done" && lastFinished.result?.url) {
      const r = lastFinished.result;
      toast({
        kind: "ok",
        text: t("yt.done"),
        hint: r.thumbnail_error ?? undefined,
        action: { label: t("yt.open"), run: () => window.open(r.url, "_blank", "noopener") },
      });
    }
    const stillRendering = jobs.some((j) => j.kind === "render" && j.project_id === id && isActive(j));
    if (lastFinished.kind === "render" && lastFinished.status === "done" && !stillRendering) {
      const n = lastFinished.params?.batch_count ?? 1;
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
  const renderJobs = activeJobs.filter((j) => j.kind === "render");
  const renderJob = renderJobs.find((j) => j.status === "running") ?? renderJobs[0];
  const pipelineJob = activeJobs.find((j) => !["render", "facecam", "titles", "montage"].includes(j.kind)) ?? null;
  const llmJob = activeJobs.find((j) => j.kind === "analyze" || j.kind === "titles") ?? null;
  const lastAnalyze =
    projectJobs.filter((j) => j.kind === "analyze" && !isActive(j)).sort((a, b) => (b.finished ?? 0) - (a.finished ?? 0))[0] ?? null;
  const facecamJob = activeJobs.find((j) => j.kind === "facecam");
  const exportJobs = activeJobs.filter((j) => j.kind === "export" || j.kind === "upload");

  const cands = project?.highlights?.candidates ?? [];
  const selected = cands.find((c) => c.id === selectedId) ?? null;
  const review = project?.review;
  const accepted = useMemo(() => new Set(review?.accepted ?? []), [review]);
  const options: ClipOptions = review?.options ?? {
    layout: "auto", subtitles: "bold", hook: true, hook_flash: false, subtitle_lang: "", profanity: "auto",
    profanity_captions: true, bleep_sound: "classic", speaker_colors: true, speaker_names: false,
    cuts: "off", zoom: "off", music: false, brand: false, loop: false,
  };
  const [voicesRev, setVoicesRev] = useState(0);
  const rejected = useMemo(() => new Set(review?.rejected ?? []), [review]);
  const edit: ClipEdit | undefined = selected ? review?.edits?.[selected.id] : undefined;
  const range = selected ? effectiveRange(selected, edit) : null;
  const musicChoice = selected && review?.music && selected.id in review.music ? review.music[selected.id] : undefined;
  const activeBrand = brand?.presets.find((b) => b.id === brand.active) ?? null;
  const plan = usePlan(id, selected?.id ?? null, {
    options,
    edit,
    music: musicChoice === undefined ? null : musicChoice,
    rev: (activeBrand?.rev ?? 0) + tracks.length * 1000 + voicesRev * 100000,
  });
  // A seamless loop moves the end to its seam (and a start out of a word): preview what the render does.
  const shownRange = renderRange(range, options, plan);
  const subLangs = [...new Set(cands.flatMap((c) => c.subtitle_languages ?? []))].filter((l) => l !== project?.language);
  const hookText = selected ? review?.hooks[selected.id] ?? selected.default_hook : "";
  const hookEdited = !!(selected && review?.hooks[selected.id] != null);
  const aiHook = !!selected?.publish.hook_text;
  const hookMode: HookMode = options.hook ? (options.hook_flash ? "both" : "text") : options.hook_flash ? "flash" : "off";

  // Words around the selected clip (transcript editor; the live preview uses the clip's part)
  const ctxFrom = selected ? Math.max(0, Math.min(selected.start, range!.start) - 12) : 0;
  const ctxTo = selected ? Math.max(selected.end, range!.end) + 12 : 0;
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    api.words(id, ctxFrom, ctxTo).then((w) => !cancelled && setWords(w)).catch(() => setWords([]));
    return () => {
      cancelled = true;
    };
  }, [id, selected?.id, Math.round(ctxFrom), Math.round(ctxTo), voicesRev]); // eslint-disable-line react-hooks/exhaustive-deps
  const previewWords = useMemo(() => {
    if (plan) return plan.words.filter((w) => !w.removed).map((w) => (w.bleep && plan.mask_captions ? { ...w, word: maskWord(w.word) } : w));
    if (!range) return [];
    return words.filter((w) => (w.start + w.end) / 2 >= range.start && (w.start + w.end) / 2 <= range.end);
  }, [plan, words, range?.start, range?.end]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the 9:16 preview as tall as the 16:9 player on wide screens.
  useEffect(() => {
    const el = playerBox.current;
    if (!el) return;
    // The preview's width feeds back into the player's size; ignore the 1-3 px ripple that
    // would otherwise make the two resize each other forever.
    const ro = new ResizeObserver(() =>
      setPreviewH((cur) => {
        const next = window.innerWidth > 720 ? el.clientHeight : null;
        return cur != null && next != null && Math.abs(cur - next) < 3 ? cur : next;
      }),
    );
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
      v.currentTime = range?.start ?? selected.start;
      setTime(range?.start ?? selected.start);
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
    const on = () => setTime(v.currentTime);
    const onPause = () => {
      setPlayingClip(false);
      setLoopPlay(false);
    };
    v.addEventListener("timeupdate", on);
    v.addEventListener("seeked", on);
    v.addEventListener("pause", onPause);
    return () => {
      v.removeEventListener("timeupdate", on);
      v.removeEventListener("seeked", on);
      v.removeEventListener("pause", onPause);
    };
  }, [playingClip, selected, project?.highlights]);

  usePreviewPlayback(
    video,
    playingClip,
    plan,
    shownRange?.end ?? null,
    () => setPlayingClip(false),
    loopPlay && shownRange ? shownRange.start : null,
  );

  /** Loop preview: from 3 s before the seam, the end plays into the start, repeating. */
  const loopPreview = () => {
    const v = video.current;
    if (!v || !shownRange) return;
    v.currentTime = Math.max(shownRange.start, shownRange.end - 3);
    setLoopPlay(true);
    setPlayingClip(true);
    v.play().catch(() => {
      setPlayingClip(false);
      setLoopPlay(false);
    });
  };

  const seek = (s: number) => {
    const v = video.current;
    if (v) v.currentTime = s;
    setTime(s);
  };

  const rangeOf = (c: Candidate) => effectiveRange(c, review?.edits?.[c.id]);

  const select = (c: Candidate, play = false) => {
    setSelectedId(c.id);
    seek(rangeOf(c).start);
    if (play) playClip(c);
    document.querySelector(`[data-cand="${c.id}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  const playClip = (c: Candidate | null = selected) => {
    const v = video.current;
    if (!v || !c) return;
    const r = c.id === selected?.id && shownRange ? shownRange : rangeOf(c);
    if (c.id !== selected?.id || v.currentTime < r.start - 0.5 || v.currentTime >= r.end - 0.2) v.currentTime = r.start;
    setPlayingClip(true);
    v.play().catch(() => setPlayingClip(false));
  };

  const playPause = () => {
    if (playingClip || (video.current && !video.current.paused)) video.current?.pause();
    else playClip();
  };

  const seekBy = (s: number) => seek(Math.max(0, Math.min(project?.duration ?? 1e9, (video.current?.currentTime ?? time) + s)));

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

  const snapshot = (): Snapshot => ({
    accepted: review?.accepted ?? [],
    rejected: review?.rejected ?? [],
    edits: review?.edits ?? {},
  });

  const setAccepted = (cid: string, v: boolean) => {
    history.push(snapshot());
    const next = new Set(accepted);
    if (v) next.add(cid);
    else next.delete(cid);
    // keep rank order
    patchReview({
      accepted: cands.filter((c) => next.has(c.id)).map((c) => c.id),
      rejected: (review?.rejected ?? []).filter((x) => !(v && x === cid)),
    });
  };

  const decide = (cid: string, keep: boolean) => {
    history.push(snapshot());
    const acc = new Set(accepted);
    const rej = new Set(rejected);
    if (keep) {
      acc.add(cid);
      rej.delete(cid);
    } else {
      acc.delete(cid);
      rej.add(cid);
    }
    patchReview({ accepted: cands.filter((c) => acc.has(c.id)).map((c) => c.id), rejected: [...rej] });
  };

  const setEdit = (cid: string, e: ClipEdit) => {
    history.push(snapshot());
    const edits = { ...(review?.edits ?? {}) };
    if (e.start == null && e.end == null && !e.deleted?.length) delete edits[cid];
    else edits[cid] = e;
    patchReview({ edits });
  };

  const setMusicChoice = (cid: string, v: string | null) => {
    const music = { ...(review?.music ?? {}) };
    if (v == null) delete music[cid];
    else music[cid] = v;
    patchReview({ music });
  };

  const undo = () => {
    const prev = history.undo(snapshot());
    if (prev) patchReview(prev);
  };

  const redo = () => {
    const next = history.redo(snapshot());
    if (next) patchReview(next);
  };

  const addManual = async () => {
    if (marks.in == null || marks.out == null) return;
    try {
      const r = await api.addManualClip(id, marks.in, marks.out);
      setMarks({ in: null, out: null });
      toast({ kind: "ok", text: t("manual.added", { n: r.candidate.rank }), hint: r.job ? t("manual.analyzing") : undefined });
      await load();
      setSelectedId(r.candidate.id);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const deleteManual = async (c: Candidate) => {
    if (!window.confirm(t("manual.delete_confirm", { n: c.rank }))) return;
    try {
      await api.deleteManualClip(id, c.id);
      load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message });
    }
  };

  const setOption = (o: Partial<ClipOptions>) => patchReview({ options: { ...options, ...o } });

  const setHook = (text: string) => {
    if (!selected || !review) return;
    const hooks = { ...review.hooks };
    if (text.trim() && text !== selected.default_hook) hooks[selected.id] = text;
    else delete hooks[selected.id];
    patchReview({ hooks }, true);
  };

  const saveFacecam = (fc: Facecam | null, remember = true) => {
    setFacecamOpen(false);
    patchReview({ facecam: fc, facecam_checked: true });
    // remembered for this channel + resolution: new projects start with it
    if (fc && remember) api.setFacecam(id, fc, { remember: true }).catch(() => {});
  };

  // Play a short part of the source (swear review list / waveform).
  const stopAt = useRef<number | null>(null);
  const playRange = (a: number, b: number) => {
    const v = video.current;
    if (!v) return;
    setPlayingClip(false);
    v.currentTime = Math.max(0, a);
    stopAt.current = b;
    v.play().catch(() => {});
    const tick = () => {
      if (stopAt.current == null) return;
      if (v.currentTime >= stopAt.current || v.paused) {
        if (!v.paused) v.pause();
        stopAt.current = null;
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
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

  const chooseGame = async (choice: GameChoice) => {
    try {
      await api.setGame(id, choice); // re-runs the highlight analysis
      load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const analyzeAI = async () => {
    try {
      await api.analyze(id, outLang ?? undefined);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const importChat = async (file: File | undefined) => {
    if (!file) return;
    try {
      const c = await api.importChat(id, file);
      toast({ kind: "ok", text: t("project.chat_count", { n: c.count }), hint: t("settings.triggers_note") });
      load();
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

  // Keyboard shortcuts ("?" shows them). Fast review has its own while it is open.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing(e) || facecamOpen || exportIds || uploadFor || publishFor || keysOpen || fastOpen) return;
      const onVideo = (e.target as HTMLElement)?.tagName === "VIDEO";
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && (k === "z" || k === "y")) {
        e.preventDefault();
        if (k === "y" || e.shiftKey) redo();
        else undo();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "?") setKeysOpen(true);
      else if (e.key === "ArrowDown" || e.key === "ArrowRight") !onVideo && (e.preventDefault(), step(1));
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") !onVideo && (e.preventDefault(), step(-1));
      else if (k === "a" && selected) decide(selected.id, true);
      else if (k === "x" && selected) decide(selected.id, false);
      else if ((e.key === " " && !onVideo) || k === "k") (e.preventDefault(), playPause());
      else if (k === "j") seekBy(e.shiftKey ? -1 : -3);
      else if (k === "l") seekBy(e.shiftKey ? 1 : 3);
      else if (k === "i") setMarks((m) => ({ ...m, in: video.current?.currentTime ?? time }));
      else if (k === "o") setMarks((m) => ({ ...m, out: video.current?.currentTime ?? time }));
      else if (k === "f" && cands.length) {
        setFastOpen(true);
        if (selected) select(selected, true);
      }
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
  const fcUnsure = !!fc && fc.source === "auto" && (fc.confidence ?? 1) < 0.6;
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
            {project.chat?.status === "ok" && (
              <span className="chip chip-outline" title={project.chat.source}>
                <Icon name="hash" size={12} />
                {t("project.chat_count", { n: project.chat.count })}
              </span>
            )}
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
            {mode === "gaming" && project.game && (
              <div className="ai-group">
                <select
                  className="select select-sm game-select"
                  value={project.game.choice}
                  onChange={(e) => chooseGame(e.target.value as GameChoice)}
                  aria-label={t("game.label")}
                  title={whyText(t, project.game.why, project.game.detected)}
                  disabled={!!pipelineJob}
                >
                  <option value="auto">
                    {project.game.detected ? t("game.auto_detected", { name: GAME_NAMES[project.game.detected] }) : t("game.auto_none")}
                  </option>
                  <option value="delta_force">{GAME_NAMES.delta_force}</option>
                  <option value="lol">{GAME_NAMES.lol}</option>
                  <option value="other">{t("game.other")}</option>
                </select>
                <a className="btn btn-sm btn-ghost icon-btn" href={href.game(id)} title={t("game.title")} aria-label={t("game.title")}>
                  <Icon name="gamepad" />
                </a>
              </div>
            )}
            <button className="btn btn-sm" onClick={reanalyze} disabled={!!pipelineJob}>
              <Icon name="refresh" />
              {project.highlights ? t("project.reanalyze") : t("project.analyze")}
            </button>
            {project.highlights && meta?.llm.available && (
              <div className="ai-group">
                <select
                  className="select select-sm"
                  value={outLang ?? project.output_language}
                  onChange={(e) => setOutLang(e.target.value)}
                  aria-label={t("project.out_lang")}
                  title={t("project.out_lang")}
                >
                  {UI_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name}
                    </option>
                  ))}
                </select>
                <button className="btn btn-sm btn-gold" onClick={analyzeAI} disabled={!!pipelineJob || !!llmJob}>
                  <Icon name="sparkles" />
                  {project.analysis ? t("project.ai_again") : t("publish.analyze")}
                </button>
              </div>
            )}
            {project.highlights && (
              <a className="btn btn-sm" href={href.stories(id)} title={t("story.button_hint")}>
                <Icon name="book" />
                {t("story.button")}
              </a>
            )}
            {project.highlights && (
              <a className="btn btn-sm" href={href.bestof(id)}>
                <Icon name="layers" />
                {t("bestof.button")}
                {project.exports > 0 && <span className="count mono">{project.exports}</span>}
              </a>
            )}
            <button className="btn btn-sm btn-ghost" onClick={() => chatInput.current?.click()} title={t("project.chat_hint")}>
              <Icon name="upload" />
              {t("project.chat_import")}
            </button>
            <input
              ref={chatInput}
              type="file"
              hidden
              accept=".json,.txt,.log,.csv"
              onChange={(e) => {
                importChat(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
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
                      <video ref={video} src={urls.source(id)} controls playsInline preload="metadata" aria-label={project.title} />
                    ) : (
                      <div className="skeleton skeleton-fill" aria-label={t("common.loading")} />
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
                        range={shownRange}
                        options={options}
                        facecam={fc}
                        words={previewWords}
                        lang={project.language}
                        hookText={hookText}
                        zoom={plan && plan.zoom_level > 1 ? { pulses: plan.pulses, level: plan.zoom_level } : null}
                        brand={options.brand ? activeBrand : null}
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
                    <Icon name={loopPlay ? "repeat" : "pause"} />
                    {loopPlay ? t("loop.stop") : t("player.stop")}
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
                {selected && shownRange && (
                  <span className="tc" style={{ marginInlineStart: 4 }}>
                    #{String(selected.rank).padStart(2, "0")} · {fmtTime(shownRange.start)} – {fmtTime(shownRange.end)}
                    {options.loop && plan?.loop && <Icon name="repeat" size={12} />}
                  </span>
                )}
                <span style={{ flex: 1 }} />
                <span className="tc">
                  {fmtTime(time, true)} / {fmtTime(project.duration)}
                </span>
                <button className="btn btn-sm btn-ghost" onClick={() => setMarks((m) => ({ ...m, in: video.current?.currentTime ?? time }))} title={t("manual.mark_in_hint")}>
                  <kbd>I</kbd>
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => setMarks((m) => ({ ...m, out: video.current?.currentTime ?? time }))} title={t("manual.mark_out_hint")}>
                  <kbd>O</kbd>
                </button>
                <button className="btn btn-sm btn-ghost icon-btn" onClick={() => setKeysOpen(true)} title={t("keys.title")} aria-label={t("keys.title")}>
                  <kbd>?</kbd>
                </button>
              </div>
              {(marks.in != null || marks.out != null) && (
                <div className="mark-bar">
                  <Icon name="scan" size={14} />
                  <span>
                    {t("manual.in")} <b className="tc">{marks.in != null ? fmtTime(marks.in, true) : "–"}</b>
                  </span>
                  <span>
                    {t("manual.out")} <b className="tc">{marks.out != null ? fmtTime(marks.out, true) : "–"}</b>
                  </span>
                  {marks.in != null && marks.out != null && (
                    <span className="muted tc">{num(Math.round(Math.abs(marks.out - marks.in) * 10) / 10)} s</span>
                  )}
                  <span style={{ flex: 1 }} />
                  <button
                    className="btn btn-sm btn-primary"
                    disabled={marks.in == null || marks.out == null || Math.abs(marks.out - marks.in) < 2}
                    onClick={addManual}
                  >
                    <Icon name="plus" />
                    {t("manual.add")}
                  </button>
                  <button className="btn btn-sm btn-ghost icon-btn" onClick={() => setMarks({ in: null, out: null })} aria-label={t("common.cancel")}>
                    <Icon name="x" />
                  </button>
                </div>
              )}
            </section>

            {selected && (
              <TranscriptEditor
                words={words}
                cand={selected}
                edit={edit}
                plan={plan}
                time={time}
                lang={project.language}
                onChange={(e) => setEdit(selected.id, e)}
                onSeek={seek}
                onUndo={undo}
                onRedo={redo}
                canUndo={history.canUndo}
                canRedo={history.canRedo}
              />
            )}
            {selected && plan && (
              <SwearReview
                projectId={id}
                plan={plan}
                edit={edit}
                lang={project.language}
                onChange={(e) => setEdit(selected.id, e)}
                onPlay={playRange}
              />
            )}

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
                  marks={marks}
                  onSeek={(s, c) => {
                    if (c && c.id !== selectedId) setSelectedId(c.id);
                    seek(s);
                  }}
                />
              </section>
            )}

            <div className="lower-grid">
              <SignalStats cand={selected} project={project} />
              <PublishPanel
                cand={selected}
                projectId={id}
                llmAvailable={!!meta?.llm.available}
                llmJob={llmJob}
                lastAnalyze={lastAnalyze}
                onAnalyze={analyzeAI}
              />
            </div>
          </div>

          <aside className="card proj-side">
            <div className="side-tabs">
              <div className="side-tablist" role="tablist">
                <button role="tab" aria-selected={tab === "cands"} onClick={() => setTab("cands")}>
                  {t("cands.tab")} <span className="count mono">{cands.length}</span>
                </button>
                <button role="tab" aria-selected={tab === "clips"} onClick={() => setTab("clips")}>
                  {t("clips.tab")} <span className="count mono">{clips.length}</span>
                </button>
              </div>
              <span style={{ flex: 1 }} />
              {tab === "cands" && accepted.size > 0 && (
                <span className="chip chip-success" style={{ alignSelf: "center" }}>
                  {t("cands.accepted", { n: accepted.size })}
                </span>
              )}
              {tab === "cands" && cands.length > 0 && (
                <button
                  className="btn btn-sm btn-ghost icon-btn"
                  style={{ alignSelf: "center" }}
                  onClick={() => {
                    setFastOpen(true);
                    if (selected) select(selected, true);
                  }}
                  title={`${t("fast.title")} (F)`}
                  aria-label={t("fast.open")}
                >
                  <Icon name="layers" />
                </button>
              )}
            </div>

            {tab === "cands" ? (
              <>
                <div className="side-scroll" role="list" aria-label={t("cands.tab")}>
                  {cands.map((c) => (
                    <CandidateRow
                      key={c.id}
                      c={c}
                      selected={c.id === selectedId}
                      accepted={accepted.has(c.id)}
                      rejected={rejected.has(c.id)}
                      edited={!!review?.edits?.[c.id]}
                      onSelect={() => select(c)}
                      onAccept={(v) => setAccepted(c.id, v)}
                      onDelete={c.manual ? () => deleteManual(c) : undefined}
                    />
                  ))}
                </div>
                <div className="render-panel">
                  <div className="render-row">
                    <label htmlFor="subs-sel">{t("render.subtitles")}</label>
                    <div className="edit-cell">
                      <select
                        id="subs-sel"
                        className="select select-sm"
                        value={options.subtitles}
                        onChange={(e) => setOption({ subtitles: e.target.value as SubtitleStyle })}
                      >
                        {SUBS.map((st) => (
                          <option key={st} value={st}>
                            {t(`sub.${st}`)}
                          </option>
                        ))}
                      </select>
                      {options.subtitles !== "none" && (
                        <div className="edit-line">
                          <label className="edit-check" title={t("render.speaker_colors_hint")}>
                            <input
                              type="checkbox"
                              checked={options.speaker_colors ?? true}
                              onChange={(e) => setOption({ speaker_colors: e.target.checked })}
                            />
                            {t("render.speaker_colors")}
                          </label>
                          <label className="edit-check">
                            <input
                              type="checkbox"
                              checked={options.speaker_names ?? false}
                              onChange={(e) => setOption({ speaker_names: e.target.checked })}
                            />
                            {t("render.speaker_names")}
                          </label>
                        </div>
                      )}
                    </div>
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
                    <Segmented<HookMode>
                      value={hookMode}
                      options={HOOK_MODES.map((m) => ({ value: m, label: t(`hook.${m}`) }))}
                      onChange={(m) => setOption({ hook: m === "text" || m === "both", hook_flash: m === "flash" || m === "both" })}
                      label={t("render.hook")}
                    />
                  </div>
                  {options.hook && (
                    <div className="render-row">
                      <label htmlFor="hook-text">
                        {hookEdited ? (
                          <span className="hook-badge">{t("render.hook_edited")}</span>
                        ) : (
                          aiHook && (
                            <span className="hook-badge ai">
                              <Icon name="sparkles" size={11} />
                              {t("render.hook_ai")}
                            </span>
                          )
                        )}
                      </label>
                      <div className="hook-row">
                        <input
                          id="hook-text"
                          className="input"
                          style={{ height: 32, fontSize: 13 }}
                          dir="auto"
                          disabled={!selected}
                          value={hookText}
                          maxLength={120}
                          placeholder={t("render.hook_placeholder")}
                          onChange={(e) => setHook(e.target.value)}
                          aria-label={t("render.hook_placeholder")}
                        />
                        {hookEdited && (
                          <button
                            className="btn btn-sm btn-ghost icon-btn"
                            onClick={() => setHook("")}
                            aria-label={t("render.hook_reset")}
                            title={t("render.hook_reset")}
                          >
                            <Icon name="refresh" />
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  {options.hook_flash && (
                    <p className="muted render-note">
                      <Icon name="sparkles" size={12} /> {t("render.flash")}: {t("render.flash_hint")}
                    </p>
                  )}
                  {subLangs.length > 0 && (
                    <div className="render-row">
                      <label htmlFor="sublang-sel">{t("render.sub_lang")}</label>
                      <select
                        id="sublang-sel"
                        className="select select-sm"
                        value={options.subtitle_lang}
                        onChange={(e) => setOption({ subtitle_lang: e.target.value })}
                      >
                        <option value="">{t("render.sub_lang_spoken", { lang: langName ?? "" })}</option>
                        {subLangs.map((l) => (
                          <option key={l} value={l}>
                            {UI_LANGUAGES.find((x) => x.code === l)?.name ?? l}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <EditTools
                    options={options}
                    setOption={setOption}
                    plan={plan}
                    tracks={tracks}
                    musicChoice={musicChoice}
                    setMusicChoice={(v) => selected && setMusicChoice(selected.id, v)}
                    brand={brand}
                    hasClip={!!selected}
                    onLoopPreview={loopPreview}
                  />
                  <div className="facecam-line">
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Icon name="camera" size={14} />
                      {t("facecam.label")}:{" "}
                      {facecamJob ? (
                        <>
                          <span className="spinner" style={{ width: 12, height: 12 }} /> {t("facecam.detecting")}
                        </>
                      ) : fc ? (
                        fcUnsure ? (
                          <span className="warn-text">{t("facecam.unsure")}</span>
                        ) : (
                          <span className="gold">
                            {fc.source === "manual"
                              ? t("facecam.manual")
                              : fc.source === "remembered"
                                ? t("facecam.remembered")
                                : t("facecam.detected")}
                          </span>
                        )
                      ) : (
                        t("facecam.none")
                      )}
                    </span>
                    <button className={`btn btn-sm ${fcUnsure ? "" : "btn-ghost"}`} onClick={() => setFacecamOpen(true)} disabled={!!facecamJob}>
                      <Icon name="scan" />
                      {fcUnsure ? t("facecam.pick") : t("common.edit")}
                    </button>
                  </div>
                  <VoicesPanel
                    projectId={id}
                    jobs={projectJobs}
                    llm={!!meta?.llm.available}
                    onDone={() => setVoicesRev((r) => r + 1)}
                    toast={(x) => toast(x)}
                  />
                  {/* pinned to the bottom of the panel: the settings above scroll, the buttons stay */}
                  <div className="render-actions">
                    {renderJob ? (
                      <div style={{ display: "grid", gap: 6 }}>
                        <JobLine job={renderJob} onCancel={() => api.queueCancel({ project_id: id, kind: "render" })} />
                        <a className="muted render-note" href={href.queue}>
                          {renderJobs.length > 1 ? t("render.in_queue", { n: renderJobs.length }) : t("bestof.see_queue")}
                        </a>
                      </div>
                    ) : (
                      <button className="btn btn-primary btn-lg btn-block" disabled={!accepted.size} onClick={render}>
                        <Icon name="film" />
                        {accepted.size ? t("render.button", { n: accepted.size }) : t("render.none")}
                      </button>
                    )}
                    <button
                      className="btn btn-block"
                      disabled={!cands.length}
                      onClick={() => setExportIds(accepted.size ? [...accepted] : selected ? [selected.id] : [])}
                      title={t("export.button_hint")}
                    >
                      <Icon name="download" />
                      {t("export.open")}
                    </button>
                    {exportJobs.length > 0 && (
                      <a className="muted render-note" href={href.queue}>
                        {t("export.in_queue", { n: exportJobs.length })}
                      </a>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="side-scroll">
                {clips.length > 0 && (
                  <div className="cal-hint">
                    <Icon name="chart" size={14} />
                    {project.calibration.calibrated ? (
                      <span>{t("cal.calibrated_n", { n: project.calibration.model_points })}</span>
                    ) : (
                      <span>{t("cal.progress", { n: project.calibration.n, need: project.calibration.needed })}</span>
                    )}
                    <a href={href.stats}>{t("nav.stats")}</a>
                  </div>
                )}
                {clips.length === 0 && clipExports.length === 0 ? (
                  <p className="muted" style={{ padding: 16 }}>
                    {t("clips.empty")}
                  </p>
                ) : (
                  <div className="clips-grid">
                    {clips.map((c) => (
                      <div className="clip-card" key={c.id}>
                        <video src={urls.clip(id, c.id, c.rendered_at)} controls playsInline preload="metadata" loop={!!c.options.loop} />
                        <div className="foot">
                          <div style={{ display: "grid", minWidth: 0 }}>
                            <span className="tc">
                              #{String(c.rank).padStart(2, "0")} · {num(Math.round(c.duration))} s
                            </span>
                            <span className="muted" style={{ fontSize: 11 }} title={`${c.encoder} · ${fmtBytes(c.size_bytes)}`}>
                              {t("clips.rendered", { when: relTime(c.rendered_at) })}
                            </span>
                            {c.edits?.loop && (
                              <span
                                className={`chip ${c.edits.loop.audio_seam?.ok === false ? "chip-outline warn-text" : "chip-outline"} loop-chip`}
                                title={
                                  c.edits.loop.audio_seam
                                    ? t("loop.measured", {
                                        click: num(c.edits.loop.audio_seam.click_ratio, 2),
                                        step: num(c.edits.loop.audio_seam.loudness_step_lu, 1),
                                      })
                                    : t("loop.label")
                                }
                              >
                                <Icon name="repeat" size={11} />
                                {c.edits.loop.audio_seam?.ok === false ? t("loop.seam_check") : t("loop.seamless")}
                              </span>
                            )}
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
                        <div className="clip-pub">
                          <button className="btn btn-sm btn-ghost" onClick={() => setExportIds([c.id])}>
                            <Icon name="download" />
                            {t("export.short")}
                          </button>
                          <button className="btn btn-sm btn-ghost" onClick={() => setPublishFor(c.id)} title={t("pub.publish_hint")}>
                            <Icon name="calendar" />
                            {t("pub.publish_btn")}
                          </button>
                          <button className="btn btn-sm btn-ghost" onClick={() => setUploadFor({ cid: c.id })}>
                            <Icon name="upload" />
                            YouTube
                          </button>
                          {hookTests?.clips[c.id] ? (
                            <button className="btn btn-sm btn-ghost" onClick={() => setHookFor(c.id)} title={t("ab.open")}>
                              <Icon name="split" />
                              {t("ab.short_result", { label: hookTests.clips[c.id].winner })}
                            </button>
                          ) : (
                            <button
                              className="btn btn-sm btn-ghost"
                              disabled={jobs.some((j) => j.kind === "ab" && j.project_id === id && j.params?.clip_id === c.id && isActive(j))}
                              onClick={() =>
                                api
                                  .makeHookTest(id, c.id)
                                  .then(() => toast({ kind: "ok", text: t("ab.queued") }))
                                  .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
                              }
                              title={t("ab.make_hint")}
                            >
                              <Icon name="split" />
                              {jobs.some((j) => j.kind === "ab" && j.project_id === id && j.params?.clip_id === c.id && isActive(j))
                                ? t("ab.making")
                                : t("ab.make")}
                            </button>
                          )}
                        </div>
                        <UploadsLine uploads={uploads[c.id] ?? []} />
                        <PerformanceForm projectId={id} clip={c} onSaved={load} />
                      </div>
                    ))}
                  </div>
                )}
                {clipExports.length > 0 && (
                  <div className="exports-block">
                    <h3 className="section-title">{t("export.list_title")}</h3>
                    <ExportsList
                      projectId={id}
                      exports={clipExports}
                      onChanged={loadExports}
                      onUpload={(cid, source) => setUploadFor({ cid, source })}
                    />
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      )}

      {exportIds && (
        <ExportDialog
          projectId={id}
          candidates={cands}
          initial={exportIds}
          spokenLang={project.language}
          onClose={() => setExportIds(null)}
        />
      )}
      {publishFor && <PublishSetupDialog projectId={id} clipId={publishFor} onClose={() => setPublishFor(null)} onDone={load} />}
      {uploadFor && cands.find((c) => c.id === uploadFor.cid) && (
        <UploadDialog
          projectId={id}
          cand={cands.find((c) => c.id === uploadFor.cid)!}
          clip={project.clips[uploadFor.cid] ?? null}
          exports={clipExports}
          initialSource={uploadFor.source}
          hookTest={hookTests?.clips[uploadFor.cid] ?? null}
          realTest={hookTests?.real_test ?? null}
          uploads={uploads[uploadFor.cid] ?? []}
          onClose={() => setUploadFor(null)}
        />
      )}
      {hookFor && hookTests?.clips[hookFor] && cands.find((c) => c.id === hookFor) && (
        <HookTestDialog
          projectId={id}
          cand={cands.find((c) => c.id === hookFor)!}
          test={hookTests.clips[hookFor]}
          realTest={hookTests.real_test}
          busy={jobs.some((j) => j.kind === "ab" && j.project_id === id && j.params?.clip_id === hookFor && isActive(j))}
          onUpload={(source) => {
            setHookFor(null);
            setUploadFor({ cid: hookFor, source });
          }}
          onChanged={loadExports}
          onClose={() => setHookFor(null)}
        />
      )}
      {fastOpen && (
        <FastReview
          candidates={cands}
          current={selected}
          accepted={accepted}
          rejected={rejected}
          playing={playingClip}
          preview={
            <VerticalPreview
              video={video}
              clip={selected}
              range={shownRange}
              options={options}
              facecam={fc}
              words={previewWords}
              lang={project.language}
              hookText={hookText}
              zoom={plan && plan.zoom_level > 1 ? { pulses: plan.pulses, level: plan.zoom_level } : null}
              brand={options.brand ? activeBrand : null}
            />
          }
          onSelect={(c) => select(c, true)}
          onDecide={(c, keep) => decide(c.id, keep)}
          onUndo={undo}
          onPlayPause={playPause}
          onSeekBy={seekBy}
          onHelp={() => setKeysOpen(true)}
          onRender={() => {
            setFastOpen(false);
            render();
          }}
          onClose={() => {
            setFastOpen(false);
            video.current?.pause();
          }}
        />
      )}
      {keysOpen && <ShortcutSheet onClose={() => setKeysOpen(false)} />}
      {facecamOpen && (
        <FacecamEditor
          projectId={id}
          time={selected?.peak ?? (project.duration ?? 0) / 2}
          initial={fc}
          onClose={() => setFacecamOpen(false)}
          onSave={saveFacecam}
          onDetect={() => {
            setFacecamOpen(false);
            api.detectFacecam(id, true).catch((e) => toast({ kind: "err", text: e.message }));
          }}
        />
      )}
    </main>
  );
}
