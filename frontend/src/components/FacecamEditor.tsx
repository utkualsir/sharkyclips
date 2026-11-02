import { useEffect, useRef, useState } from "react";
import { api, urls, type Facecam, type FacecamAnalysis } from "../api";
import { clamp } from "../format";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Modal } from "./ui";

type Rect = { x: number; y: number; w: number; h: number };
type Drag =
  | { kind: "move"; sx: number; sy: number; start: Rect }
  | { kind: "resize"; handle: string; start: Rect }
  | { kind: "draw"; ox: number; oy: number };

const MIN = 0.04;

/** Drag a rectangle over a video frame to set the facecam region (normalized 0..1). */
export default function FacecamEditor({
  projectId,
  time,
  initial,
  onSave,
  onDetect,
  onClose,
}: {
  projectId: string;
  time: number;
  initial: Facecam | null;
  onSave: (fc: Facecam | null, remember: boolean) => void;
  onDetect: () => void;
  onClose: () => void;
}) {
  const { t, num } = useI18n();
  const stage = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<Rect | null>(initial ? { x: initial.x, y: initial.y, w: initial.w, h: initial.h } : null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [analysis, setAnalysis] = useState<FacecamAnalysis | null>(null);
  const [remember, setRemember] = useState(true);
  useEffect(() => {
    api.facecamAnalysis(projectId).then(setAnalysis).catch(() => setAnalysis(null));
  }, [projectId]);
  // The detection's own frame (a moment with the face) when it has candidates to pick from.
  const cands = analysis?.frame ? analysis.candidates.slice(0, 4) : [];
  const frameUrl = cands.length ? urls.facecamFrame(projectId, analysis?.created_at ?? "") : urls.frame(projectId, time);
  const pick = (c: Rect) => setRect({ x: c.x, y: c.y, w: c.w, h: c.h });
  const same = (a: Rect, b: Rect | null) => !!b && Math.abs(a.x - b.x) < 0.005 && Math.abs(a.y - b.y) < 0.005 && Math.abs(a.w - b.w) < 0.005;

  const point = (e: React.PointerEvent) => {
    const r = stage.current!.getBoundingClientRect();
    return { x: clamp((e.clientX - r.left) / r.width, 0, 1), y: clamp((e.clientY - r.top) / r.height, 0, 1) };
  };

  const down = (e: React.PointerEvent) => {
    const target = e.target as HTMLElement;
    const p = point(e);
    stage.current!.setPointerCapture(e.pointerId);
    if (target.dataset.h && rect) setDrag({ kind: "resize", handle: target.dataset.h, start: rect });
    else if (target.classList.contains("fc-rect") && rect) setDrag({ kind: "move", sx: p.x, sy: p.y, start: rect });
    else {
      setDrag({ kind: "draw", ox: p.x, oy: p.y });
      setRect({ x: p.x, y: p.y, w: 0, h: 0 });
    }
  };

  const move = (e: React.PointerEvent) => {
    if (!drag) return;
    const p = point(e);
    if (drag.kind === "move") {
      const s = drag.start;
      setRect({ ...s, x: clamp(s.x + p.x - drag.sx, 0, 1 - s.w), y: clamp(s.y + p.y - drag.sy, 0, 1 - s.h) });
    } else if (drag.kind === "draw") {
      setRect({ x: Math.min(drag.ox, p.x), y: Math.min(drag.oy, p.y), w: Math.abs(p.x - drag.ox), h: Math.abs(p.y - drag.oy) });
    } else {
      const s = drag.start;
      let x0 = s.x, y0 = s.y, x1 = s.x + s.w, y1 = s.y + s.h;
      if (drag.handle.includes("w")) x0 = Math.min(p.x, x1 - MIN);
      if (drag.handle.includes("e")) x1 = Math.max(p.x, x0 + MIN);
      if (drag.handle.includes("n")) y0 = Math.min(p.y, y1 - MIN);
      if (drag.handle.includes("s")) y1 = Math.max(p.y, y0 + MIN);
      setRect({ x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
    }
  };

  const up = () => {
    if (drag?.kind === "draw" && rect && (rect.w < MIN || rect.h < MIN)) setRect(null);
    setDrag(null);
  };

  return (
    <Modal
      wide
      title={t("facecam.title")}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onDetect} style={{ marginInlineEnd: "auto" }}>
            <Icon name="scan" />
            {t("facecam.redetect")}
          </button>
          <button className="btn" onClick={() => onSave(null, false)}>
            {t("facecam.clear")}
          </button>
          <label className="edit-check small" title={t("facecam.remember_hint")}>
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            {t("facecam.remember")}
          </label>
          <button
            className="btn btn-primary"
            disabled={!rect}
            onClick={() => rect && onSave({ ...rect, source: "manual" }, remember)}
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted" style={{ margin: 0 }}>
        {cands.length > 1 || (analysis?.ask && cands.length) ? t("facecam.pick_help") : t("facecam.help")}
      </p>
      {analysis?.layout && (
        <p className="muted small" style={{ margin: 0 }}>
          {t("facecam.layout_known", { channel: analysis.layout.channel, res: `${analysis.layout.width}×${analysis.layout.height}` })}
        </p>
      )}
      <div
        className="fc-stage"
        ref={stage}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        dir="ltr"
        style={{ cursor: "crosshair", minHeight: loaded ? undefined : 240 }}
      >
        <img src={frameUrl} alt="" onLoad={() => setLoaded(true)} draggable={false} />
        {cands.map((c, i) => (
          <button
            key={i}
            type="button"
            className={`fc-cand${same(c, rect) ? " on" : ""}`}
            style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%`, width: `${c.w * 100}%`, height: `${c.h * 100}%` }}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => pick(c)}
            title={t("facecam.pick_this")}
          >
            <span className="fc-cand-tag">
              {i + 1} · {num(Math.round(c.confidence * 100))}%
            </span>
          </button>
        ))}
        {!loaded && (
          <div className="skeleton skeleton-fill" />
        )}
        {rect && rect.w > 0 && (
          <div
            className="fc-rect"
            style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.w * 100}%`, height: `${rect.h * 100}%` }}
          >
            <span className="fc-tag">{t("facecam.label")}</span>
            {["nw", "ne", "sw", "se"].map((h) => (
              <span key={h} className="fc-handle" data-h={h} />
            ))}
          </div>
        )}
      </div>
      {!rect && (
        <p className="muted" style={{ margin: 0, display: "flex", gap: 8, alignItems: "center" }}>
          <Icon name="scan" />
          {t("facecam.add")}
        </p>
      )}
    </Modal>
  );
}
