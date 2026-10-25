import { useRef, useState } from "react";
import { urls, type Facecam } from "../api";
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
  onSave: (fc: Facecam | null) => void;
  onDetect: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const stage = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<Rect | null>(initial ? { x: initial.x, y: initial.y, w: initial.w, h: initial.h } : null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [loaded, setLoaded] = useState(false);

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
          <button className="btn" onClick={() => onSave(null)}>
            {t("facecam.clear")}
          </button>
          <button
            className="btn btn-primary"
            disabled={!rect}
            onClick={() => rect && onSave({ ...rect, source: "manual" })}
          >
            {t("common.save")}
          </button>
        </>
      }
    >
      <p className="muted" style={{ margin: 0 }}>
        {t("facecam.help")}
      </p>
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
        <img src={urls.frame(projectId, time)} alt="" onLoad={() => setLoaded(true)} draggable={false} />
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
