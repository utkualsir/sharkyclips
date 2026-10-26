import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Candidate } from "../api";
import { SHORTCUTS, typing } from "../editing";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Modal } from "./ui";

/** Keyboard cheat sheet ("?"). */
export function ShortcutSheet({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Modal title={t("keys.title")} onClose={onClose} top>
      <div className="keys-list">
        {SHORTCUTS.map((s) => (
          <div className="keys-row" key={s.label}>
            <span className="keys-k">
              {s.keys.map((k, i) => (
                <kbd key={i}>{k}</kbd>
              ))}
            </span>
            <span>{t(s.label)}</span>
          </div>
        ))}
      </div>
      <p className="muted" style={{ margin: "14px 0 0", fontSize: 12.5 }}>
        {t("keys.note")}
      </p>
    </Modal>
  );
}

interface Props {
  candidates: Candidate[];
  current: Candidate | null;
  accepted: Set<string>;
  rejected: Set<string>;
  preview: ReactNode; // the 9:16 canvas, fed by the page's player
  playing: boolean;
  onSelect: (c: Candidate) => void;
  onDecide: (c: Candidate, accept: boolean) => void;
  onUndo: () => void;
  onPlayPause: () => void;
  onSeekBy: (s: number) => void;
  onHelp: () => void;
  onRender: () => void;
  onClose: () => void;
}

/** Fast review: one candidate at a time, full screen. Swipe right / A = keep, swipe left /
 * X = skip, then the next undecided clip plays by itself. */
export default function FastReview(p: Props) {
  const { t, num } = useI18n();
  const { candidates, current } = p;
  const [dx, setDx] = useState(0);
  const [fly, setFly] = useState<0 | 1 | -1>(0);
  const start = useRef<number | null>(null);
  const reduce = document.documentElement.dataset.motion && document.documentElement.dataset.motion !== "full";
  const idx = current ? candidates.findIndex((c) => c.id === current.id) : -1;
  const decided = candidates.filter((c) => p.accepted.has(c.id) || p.rejected.has(c.id)).length;
  const done = decided === candidates.length && candidates.length > 0;

  const decide = (accept: boolean) => {
    if (!current || fly) return;
    const c = current;
    setFly(accept ? 1 : -1);
    window.setTimeout(
      () => {
        p.onDecide(c, accept);
        setFly(0);
        setDx(0);
        const after = [...candidates.slice(idx + 1), ...candidates.slice(0, idx)].find(
          (x) => x.id !== c.id && !p.accepted.has(x.id) && !p.rejected.has(x.id),
        );
        if (after) p.onSelect(after);
      },
      reduce ? 0 : 230,
    );
  };

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (typing(e)) return;
      const k = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && k === "z") {
        e.preventDefault();
        p.onUndo();
      } else if (e.ctrlKey || e.metaKey || e.altKey) return;
      else if (k === "a") decide(true);
      else if (k === "x") decide(false);
      else if (e.key === " " || k === "k") (e.preventDefault(), p.onPlayPause());
      else if (k === "j") p.onSeekBy(e.shiftKey ? -1 : -3);
      else if (k === "l") p.onSeekBy(e.shiftKey ? 1 : 3);
      else if (e.key === "ArrowRight" && candidates[idx + 1]) p.onSelect(candidates[idx + 1]);
      else if (e.key === "ArrowLeft" && candidates[idx - 1]) p.onSelect(candidates[idx - 1]);
      else if (e.key === "Backspace") p.onUndo();
      else if (e.key === "?") p.onHelp();
      else if (e.key === "Escape") p.onClose();
      else return;
      e.stopPropagation();
    };
    window.addEventListener("keydown", on, true);
    return () => window.removeEventListener("keydown", on, true);
  });

  const title = current ? current.publish.titles[0] || current.text : "";
  const viral = current?.publish.available ? current.publish.calibrated?.score ?? current.publish.viral_score : null;
  const state = current ? (p.accepted.has(current.id) ? "kept" : p.rejected.has(current.id) ? "skipped" : null) : null;
  const shift = fly ? fly * window.innerWidth : dx;

  // A portal: the page wrapper animates with transforms, which would trap a fixed overlay.
  return createPortal(
    <div className="fast" role="dialog" aria-modal="true" aria-label={t("fast.title")}>
      <div className="fast-top">
        <span className="chip chip-outline mono">
          {idx + 1} / {candidates.length}
        </span>
        <span className="muted">{t("fast.progress", { n: decided, total: candidates.length })}</span>
        <span style={{ flex: 1 }} />
        <button className="btn btn-sm btn-ghost" onClick={p.onHelp}>
          <kbd>?</kbd> {t("keys.title")}
        </button>
        <button className="btn btn-sm btn-ghost icon-btn" onClick={p.onClose} aria-label={t("common.close")} title={`${t("common.close")} (Esc)`}>
          <Icon name="x" />
        </button>
      </div>
      {done && !current ? null : (
        <div className="fast-stage">
          <div
            className={`fast-card${fly ? " flying" : ""}`}
            style={{ transform: `translateX(${shift}px) rotate(${shift / 28}deg)` }}
            onPointerDown={(e) => {
              start.current = e.clientX;
              (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
            }}
            onPointerMove={(e) => start.current != null && setDx(e.clientX - start.current)}
            onPointerUp={() => {
              const d = dx;
              start.current = null;
              if (Math.abs(d) > 110) decide(d > 0);
              else {
                if (Math.abs(d) < 6) p.onPlayPause();
                setDx(0);
              }
            }}
          >
            <div className="fast-frame">{p.preview}</div>
            <span className="fast-stamp keep" style={{ opacity: Math.max(0, Math.min(1, shift / 110)) }}>
              {t("fast.keep")}
            </span>
            <span className="fast-stamp skip" style={{ opacity: Math.max(0, Math.min(1, -shift / 110)) }}>
              {t("fast.skip")}
            </span>
            {!p.playing && !dx && (
              <span className="fast-play" aria-hidden="true">
                <Icon name="play" size={28} />
              </span>
            )}
          </div>
          <div className="fast-info">
            {current && (
              <>
                <div className="fast-meta">
                  <span className="mono">#{String(current.rank).padStart(2, "0")}</span>
                  <span className="tc">{num(Math.round(current.duration))} s</span>
                  {viral != null && (
                    <span className="gold">
                      <Icon name="sparkles" size={12} /> {viral}/100
                    </span>
                  )}
                  <span className="muted">
                    {t("cands.hype_short")} {current.hype_score}
                  </span>
                  {current.manual && <span className="chip">{t("manual.badge")}</span>}
                  {state && <span className={`chip ${state === "kept" ? "chip-success" : "chip-danger"}`}>{t(`fast.${state}`)}</span>}
                </div>
                <p className="fast-title" dir="auto">
                  {title}
                </p>
              </>
            )}
            <div className="fast-actions">
              <button className="fast-btn skip" onClick={() => decide(false)} aria-label={t("fast.skip")} title={`${t("fast.skip")} (X)`}>
                <Icon name="x" size={26} />
              </button>
              <button className="fast-btn undo" onClick={p.onUndo} aria-label={t("tx.undo")} title={`${t("tx.undo")} (Ctrl+Z)`}>
                <Icon name="refresh" className="icon flip-x" size={20} />
              </button>
              <button className="fast-btn keep" onClick={() => decide(true)} aria-label={t("fast.keep")} title={`${t("fast.keep")} (A)`}>
                <Icon name="check" size={26} />
              </button>
            </div>
            <p className="muted fast-hint">{t("fast.hint")}</p>
            {done && (
              <div className="fast-done">
                <b>{t("fast.done", { n: p.accepted.size })}</b>
                <button className="btn btn-primary" onClick={p.onRender} disabled={!p.accepted.size}>
                  <Icon name="film" />
                  {t("render.button", { n: p.accepted.size })}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}
