import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import {
  clipState,
  endAction,
  fmtLeft,
  seekTarget,
  wrapped,
  type ClipEndMode,
} from "../clipEnd";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Sep } from "./ui";

const KEY = "sc-clip-end";
const EVT = "sc-clip-end-mode";

function readMode(): ClipEndMode {
  try {
    return localStorage.getItem(KEY) === "loop" ? "loop" : "stop";
  } catch {
    return "stop";
  }
}

/** Stop or loop at the end of a clip: one setting for every player (kept in this browser). */
export function useClipEndMode(): [ClipEndMode, (m: ClipEndMode) => void] {
  const [mode, setMode] = useState<ClipEndMode>(readMode);
  useEffect(() => {
    const on = () => setMode(readMode());
    window.addEventListener(EVT, on);
    return () => window.removeEventListener(EVT, on);
  }, []);
  const set = (m: ClipEndMode) => {
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* private window: this session only */
    }
    setMode(m);
    window.dispatchEvent(new Event(EVT));
  };
  return [mode, set];
}

/** The playhead of a video, smooth while it plays (rAF) and right after a seek. */
export function useVideoTime(video: HTMLVideoElement | null): {
  t: number;
  total: number;
  playing: boolean;
} {
  const [st, setSt] = useState({ t: 0, total: 0, playing: false });
  useEffect(() => {
    if (!video) return;
    let raf = 0;
    const read = () =>
      setSt({
        t: video.currentTime,
        total: isFinite(video.duration) ? video.duration : 0,
        playing: !video.paused && !video.ended,
      });
    const loop = () => {
      read();
      if (!video.paused) raf = requestAnimationFrame(loop);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(loop);
    };
    const evs = [
      "timeupdate",
      "seeked",
      "loadedmetadata",
      "pause",
      "ended",
      "durationchange",
    ];
    evs.forEach((e) => video.addEventListener(e, read));
    video.addEventListener("play", start);
    read();
    if (!video.paused) start();
    return () => {
      cancelAnimationFrame(raf);
      evs.forEach((e) => video.removeEventListener(e, read));
      video.removeEventListener("play", start);
    };
  }, [video]);
  return st;
}

/** Stops (or loops) a video exactly at `end` when it was playing inside the clip, and reports
 *  when it reached the end. For players that don't already do this themselves. */
export function useClipEnforcer(
  video: HTMLVideoElement | null,
  start: number,
  end: number,
  mode: ClipEndMode,
  enabled = true,
) {
  const [endedAt, setEndedAt] = useState(0);
  useEffect(() => {
    if (!video || !enabled || !(end > start)) return;
    let raf = 0;
    let prev = video.currentTime;
    const tick = () => {
      const t = video.currentTime;
      if (t >= start - 0.05) {
        const a = endAction(t, end, mode);
        if (a === "stop") {
          video.pause();
          video.currentTime = end; // stops on the last frame of the clip, not a frame after it
          setEndedAt(Date.now());
          return;
        }
        if (a === "loop") {
          video.currentTime = start;
          setEndedAt(Date.now());
        }
      }
      if (wrapped(prev, t, start, end)) setEndedAt(Date.now()); // a native loop came around
      prev = t;
      if (!video.paused) raf = requestAnimationFrame(tick);
    };
    const go = () => {
      cancelAnimationFrame(raf);
      prev = video.currentTime;
      raf = requestAnimationFrame(tick);
    };
    const onEnded = () => setEndedAt(Date.now());
    video.addEventListener("play", go);
    video.addEventListener("ended", onEnded);
    if (!video.paused) go();
    return () => {
      cancelAnimationFrame(raf);
      video.removeEventListener("play", go);
      video.removeEventListener("ended", onEnded);
    };
  }, [video, start, end, mode, enabled]);
  return endedAt;
}

/** "End of clip" - shown in the frame for a moment when the clip ends (stays while stopped there). */
export function EndBadge({ show, mode }: { show: boolean; mode: ClipEndMode }) {
  const { t } = useI18n();
  return (
    <div
      className={`clip-end-badge${show ? " on" : ""}`}
      role="status"
      aria-live="polite"
      data-testid="clip-end-badge"
    >
      {show && (
        <>
          <Icon name={mode === "loop" ? "repeat" : "stop"} size={13} />
          {mode === "loop" ? t("clipend.looped") : t("clipend.end")}
        </>
      )}
    </div>
  );
}

/** Is the "End of clip" badge on now? Briefly after a loop wrap, and while stopped at the end. */
export function useEndShown(
  endedAt: number,
  atEnd: boolean,
  playing: boolean,
  mode: ClipEndMode,
): boolean {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!endedAt) return;
    setNow(Date.now());
    const id = window.setTimeout(() => setNow(Date.now()), 1300);
    return () => window.clearTimeout(id);
  }, [endedAt]);
  if (mode === "stop" && atEnd && !playing && endedAt) return true;
  return !!endedAt && now - endedAt < 1200;
}

/** The clip's range on a progress bar: highlighted range, start + end markers, playhead, time left,
 *  the Stop / Loop setting and (optionally) a big-preview button. Click or arrow keys to seek. */
export function ClipBar({
  t: time,
  start,
  end,
  total,
  onSeek,
  mode,
  onMode,
  onBig,
  compact = false,
  extra,
}: {
  t: number;
  start: number;
  end: number;
  /** what the bar shows (the whole source video, or just the clip file) */
  total: number;
  onSeek?: (s: number) => void;
  mode: ClipEndMode;
  onMode: (m: ClipEndMode) => void;
  onBig?: () => void;
  compact?: boolean;
  extra?: ReactNode;
}) {
  const { t, num } = useI18n();
  const st = clipState(time, start, end, total);
  const track = useRef<HTMLDivElement>(null);
  const seekAt = (clientX: number) => {
    const el = track.current;
    if (!el || !onSeek) return;
    const r = el.getBoundingClientRect();
    const rtl = getComputedStyle(el).direction === "rtl";
    const x = (clientX - r.left) / Math.max(1, r.width);
    onSeek(seekTarget(rtl ? 1 - x : x, Math.max(end, total)));
  };
  const len = Math.max(0, end - start);
  return (
    <div
      className={`clipbar${compact ? " compact" : ""}`}
      data-testid="clipbar"
    >
      <div
        ref={track}
        className="clipbar-track"
        role="slider"
        tabIndex={onSeek ? 0 : -1}
        aria-label={t("clipend.bar")}
        aria-valuemin={0}
        aria-valuemax={Math.round(Math.max(end, total))}
        aria-valuenow={Math.round(time)}
        aria-valuetext={t("clipend.left", { s: fmtLeft(st.left) })}
        onPointerDown={(e) => seekAt(e.clientX)}
        onKeyDown={(e) => {
          if (!onSeek) return;
          const k = e.key;
          if (k === "ArrowRight" || k === "ArrowLeft") {
            e.preventDefault();
            onSeek(Math.max(0, time + (k === "ArrowRight" ? 1 : -1)));
          } else if (k === "Home") onSeek(start);
          else if (k === "End") onSeek(Math.max(start, end - 1));
        }}
      >
        <span
          className="clipbar-range"
          style={{
            insetInlineStart: `${st.startPct}%`,
            width: `${Math.max(0.6, st.endPct - st.startPct)}%`,
          }}
        />
        <span
          className="clipbar-done"
          style={{
            insetInlineStart: `${st.startPct}%`,
            width: `${Math.max(0, Math.min(st.playPct, st.endPct) - st.startPct)}%`,
          }}
        />
        <span
          className="clipbar-mark start"
          style={{ insetInlineStart: `${st.startPct}%` }}
          title={t("clipend.start")}
          data-testid="clip-start-mark"
        />
        <span
          className={`clipbar-mark end${st.atEnd ? " hit" : ""}`}
          style={{ insetInlineStart: `${st.endPct}%` }}
          title={t("clipend.end")}
          data-testid="clip-end-mark"
        />
        <span
          className="clipbar-head"
          style={{ insetInlineStart: `${st.playPct}%` }}
        />
      </div>
      <div className="clipbar-row">
        <span className="tc clipbar-range-text">
          {fmtTime(start, !compact)} – {fmtTime(end, !compact)}
          {!compact && (
            <span className="muted"><Sep />{num(Math.round(len * 10) / 10)} s</span>
          )}
        </span>
        <span
          className={`tc clipbar-left${st.inClip ? "" : " muted"}`}
          data-testid="clip-left"
        >
          {st.atEnd
            ? t("clipend.end")
            : st.inClip
              ? t("clipend.left", { s: fmtLeft(st.left) })
              : t("clipend.outside")}
        </span>
        <span style={{ flex: 1 }} />
        {extra}
        <button
          type="button"
          className="btn btn-xs btn-ghost clipbar-mode"
          aria-pressed={mode === "loop"}
          onClick={() => onMode(mode === "loop" ? "stop" : "loop")}
          title={t("clipend.mode_hint")}
        >
          <Icon name={mode === "loop" ? "repeat" : "stop"} size={12} />
          {mode === "loop" ? t("clipend.loop") : t("clipend.stop")}
        </button>
        {onBig && (
          <button
            type="button"
            className="btn btn-xs btn-ghost icon-btn"
            onClick={onBig}
            aria-label={t("clipend.big")}
            title={t("clipend.big")}
          >
            <Icon name="maximize" size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

/** Full screen for a box (video + our markers + badge), not the bare video (which would hide them). */
export function toggleBig(box: HTMLElement | null) {
  if (!box) return;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  else box.requestFullscreen?.().catch(() => {});
}

/** A rendered clip file (the whole file is the clip): its own end marker, time left, Stop / Loop
 *  and the "End of clip" badge, also in the big preview. */
export function ClipVideo({
  src,
  label,
  className = "",
  frameClass = "",
  children,
  autoPlay = false,
  compact = true,
  videoId,
}: {
  src: string;
  label: string;
  className?: string;
  frameClass?: string;
  children?: ReactNode;
  autoPlay?: boolean;
  compact?: boolean;
  videoId?: string;
}) {
  const [el, setEl] = useState<HTMLVideoElement | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useClipEndMode();
  const { t, total, playing } = useVideoTime(el);
  const end = total || 0;
  const endedAt = useClipEnforcer(el, 0, end, mode, end > 0);
  const shown = useEndShown(endedAt, end > 0 && t >= end - 0.05, playing, mode);
  return (
    <div className={`clip-video ${className}`.trim()} ref={box}>
      <div className={`clip-video-frame ${frameClass}`.trim()}>
        <video
          ref={setEl}
          id={videoId}
          src={src}
          controls
          controlsList="nofullscreen"
          playsInline
          preload="metadata"
          autoPlay={autoPlay}
          aria-label={label}
        />
        <EndBadge show={shown} mode={mode} />
        {children}
      </div>
      {end > 0 && (
        <ClipBar
          t={t}
          start={0}
          end={end}
          total={end}
          compact={compact}
          mode={mode}
          onMode={setMode}
          onSeek={(s) => el && (el.currentTime = Math.min(s, end))}
          onBig={() => toggleBig(box.current)}
        />
      )}
    </div>
  );
}

/** Keeps a ref'd video element in state, so hooks re-run when it appears. */
export function useVideoEl(
  ref: RefObject<HTMLVideoElement | null>,
): HTMLVideoElement | null {
  const [el, setEl] = useState<HTMLVideoElement | null>(null);
  useEffect(() => {
    if (ref.current !== el) setEl(ref.current);
  });
  return el;
}
