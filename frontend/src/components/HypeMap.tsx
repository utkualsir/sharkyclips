import { useCallback, useEffect, useRef, useState } from "react";
import type { Candidate, HypeCurve } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { cssVar } from "../theme";

interface Props {
  curve: HypeCurve;
  candidates: Candidate[];
  selected: Candidate | null;
  currentTime: number;
  onSeek: (t: number, cand: Candidate | null) => void;
}

const BAR_PX = 4; // bar + gap, in CSS pixels

/** Bar chart of the whole video's hype curve. Selected clip in gold, other candidates highlighted. */
export default function HypeMap({ curve, candidates, selected, currentTime, onSeek }: Props) {
  const { t } = useI18n();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<{ x: number; t: number; v: number } | null>(null);
  const [themeTick, setThemeTick] = useState(0);
  const duration = curve.duration;

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    const onTheme = () => setThemeTick((n) => n + 1);
    window.addEventListener("cf-theme", onTheme);
    return () => {
      ro.disconnect();
      window.removeEventListener("cf-theme", onTheme);
    };
  }, []);

  // Max-pool the curve to the number of bars that fit (peaks survive).
  const bars = useCallback(() => {
    const n = Math.max(20, Math.floor(width / BAR_PX));
    const src = curve.combined;
    const out: number[] = [];
    const per = src.length / n;
    for (let i = 0; i < n; i++) {
      let m = 0;
      const a = Math.floor(i * per);
      const b = Math.max(a + 1, Math.floor((i + 1) * per));
      for (let j = a; j < b && j < src.length; j++) m = Math.max(m, src[j]);
      out.push(m);
    }
    return out;
  }, [curve, width]);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !width) return;
    const dpr = window.devicePixelRatio || 1;
    const H = el.clientHeight;
    el.width = Math.round(width * dpr);
    el.height = Math.round(H * dpr);
    const ctx = el.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, H);
    const colBar = cssVar("--bar");
    const colCand = cssVar("--bar-cand");
    const colGold = cssVar("--gold");
    const colGoldText = cssVar("--gold-text");
    const colText = cssVar("--text");
    const colMuted = cssVar("--muted");
    const vals = bars();
    const n = vals.length;
    const bw = width / n;
    const top = 16; // room for the rank labels
    const usable = H - top - 2;
    const secPerBar = duration / n;
    const inRange = (c: { start: number; end: number }, i: number) =>
      (i + 1) * secPerBar > c.start && i * secPerBar < c.end;

    for (let i = 0; i < n; i++) {
      const h = Math.max(2, (vals[i] / 100) * usable);
      let col = colBar;
      if (selected && inRange(selected, i)) col = colGold;
      else if (candidates.some((c) => inRange(c, i))) col = colCand;
      ctx.fillStyle = col;
      const r = Math.min(1.5, Math.max(0, (bw - 1) / 2));
      ctx.beginPath();
      ctx.roundRect(i * bw + 0.5, H - h, Math.max(1, bw - 1), h, [r, r, 0, 0]);
      ctx.fill();
    }

    // Rank labels over the candidate peaks
    ctx.font = `500 10px "Geist Mono", ui-monospace, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const c of candidates) {
      const isSel = selected?.id === c.id;
      if (!isSel && candidates.length > 20 && c.rank > 10) continue;
      const x = Math.min(width - 6, Math.max(6, (c.peak / duration) * width));
      ctx.fillStyle = isSel ? colGoldText : colMuted;
      ctx.fillText(String(c.rank), x, 1);
    }

    // Playhead
    if (currentTime > 0) {
      const x = Math.round((currentTime / duration) * width) + 0.5;
      ctx.strokeStyle = colText;
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, top - 2);
      ctx.lineTo(x, H);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }, [width, bars, candidates, selected, currentTime, duration, themeTick]);

  const timeAt = (clientX: number) => {
    const rect = canvas.current!.getBoundingClientRect();
    const x = Math.min(Math.max(clientX - rect.left, 0), rect.width);
    return { x, t: (x / rect.width) * duration };
  };

  const valueAt = (time: number) => {
    const i = Math.min(curve.combined.length - 1, Math.floor(time / curve.resolution_s));
    return curve.combined[Math.max(0, i)] ?? 0;
  };

  const click = (clientX: number) => {
    const { t: time } = timeAt(clientX);
    const hit = candidates.find((c) => time >= c.start && time <= c.end) ?? null;
    onSeek(time, hit);
  };

  return (
    <div className="hype" dir="ltr">
      <canvas
        ref={canvas}
        role="slider"
        aria-label={t("hype.title")}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(currentTime)}
        aria-valuetext={fmtTime(currentTime)}
        tabIndex={0}
        onClick={(e) => click(e.clientX)}
        onMouseMove={(e) => {
          const { x, t: time } = timeAt(e.clientX);
          setHover({ x, t: time, v: valueAt(time) });
        }}
        onMouseLeave={() => setHover(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") onSeek(Math.min(duration, currentTime + 5), null);
          if (e.key === "ArrowLeft") onSeek(Math.max(0, currentTime - 5), null);
        }}
      />
      {hover && (
        <div className="hype-tip" style={{ left: Math.min(Math.max(hover.x, 40), width - 40) }}>
          <span className="tc">{fmtTime(hover.t)}</span>
          <span className="muted"> · {hover.v}</span>
        </div>
      )}
      <div className="hype-axis tc">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <span key={f}>{fmtTime(duration * f)}</span>
        ))}
      </div>
    </div>
  );
}
