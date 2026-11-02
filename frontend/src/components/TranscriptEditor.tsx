import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { Candidate, ClipEdit, EditPlanView, Word } from "../api";
import { effectiveRange, mergeRanges, speakerLabel, subtractRange, typing } from "../editing";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";

interface Props {
  words: Word[]; // the clip's words plus some context before / after (source times)
  cand: Candidate;
  edit: ClipEdit | undefined;
  plan: EditPlanView | null;
  time: number;
  lang: string | null;
  onChange: (edit: ClipEdit) => void;
  onSeek: (t: number) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

type Drag = { kind: "select"; anchor: number; moved: boolean } | { kind: "start" | "end"; at: number };

const mid = (w: Word) => (w.start + w.end) / 2;

/** Edit by transcript: click a word to jump there, drag across words to select them,
 * Delete cuts them out of the video, the [ ] handles trim the clip. */
export default function TranscriptEditor({ words, cand, edit, plan, time, lang, onChange, onSeek, onUndo, onRedo, canUndo, canRedo }: Props) {
  const { t, num } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const range = effectiveRange(cand, edit);
  const deleted = useMemo(() => edit?.deleted ?? [], [edit]);
  const joiner = lang === "zh" || lang === "ja" ? "" : " ";

  const inside = words.map((w) => mid(w) >= range.start && mid(w) <= range.end);
  const firstIn = inside.indexOf(true);
  const lastIn = inside.lastIndexOf(true);
  const isDeleted = (w: Word) => deleted.some(([a, b]) => mid(w) >= a && mid(w) <= b);
  const auto = useMemo(() => {
    const m = new Map<number, "filler" | "silence">();
    if (!plan) return m;
    for (const r of plan.removed) {
      if (r.kind === "deleted") continue;
      words.forEach((w, i) => {
        if (mid(w) >= r.a && mid(w) <= r.b) m.set(i, r.kind as "filler");
      });
    }
    return m;
  }, [plan, words]);
  const bleeped = useMemo(() => new Set((plan?.words ?? []).filter((w) => w.bleep).map((w) => w.start.toFixed(2))), [plan]);
  const maybe = useMemo(() => new Set((plan?.words ?? []).filter((w) => w.maybe).map((w) => w.start.toFixed(2))), [plan]);
  const multi = new Set(words.map((w) => w.spk).filter(Boolean)).size > 1;
  // Silence cuts that sit between two words: shown as a small marker.
  const gaps = useMemo(() => {
    const g = new Map<number, number>();
    for (const r of plan?.removed ?? []) {
      if (r.kind !== "silence") continue;
      const i = words.findIndex((w) => w.start >= r.b - 0.05);
      if (i > 0) g.set(i, (g.get(i) ?? 0) + (r.b - r.a));
    }
    return g;
  }, [plan, words]);

  const span = (i: number, j: number): [number, number] => {
    const a = words[i];
    const b = words[j];
    const prevEnd = i > 0 ? words[i - 1].end : a.start - 0.3;
    const nextStart = j + 1 < words.length ? words[j + 1].start : b.end + 0.3;
    return [Math.max(prevEnd, a.start - 0.06), Math.min(nextStart, b.end + 0.06)];
  };

  const toggleSelection = () => {
    if (!sel) return;
    const [i, j] = sel[0] <= sel[1] ? sel : [sel[1], sel[0]];
    const chosen = words.slice(i, j + 1).filter((_, k) => inside[i + k]);
    if (!chosen.length) return;
    const [a, b] = span(i, j);
    const allDeleted = chosen.every(isDeleted);
    const next = allDeleted ? subtractRange(deleted, a, b) : mergeRanges([...deleted, [a, b]]);
    onChange({ ...edit, deleted: next });
    setSel(null);
  };

  // Bleep / unbleep the selected words by hand (the swear review list shows them too).
  const bleepSelection = () => {
    if (!sel) return;
    const [i, j] = sel[0] <= sel[1] ? sel : [sel[1], sel[0]];
    const a = words[i].start - 0.02;
    const b = words[j].end + 0.02;
    const all = words.slice(i, j + 1).every((w) => bleeped.has(w.start.toFixed(2)));
    const bl = edit?.bleep ?? [];
    const un = edit?.unbleep ?? [];
    onChange(
      all
        ? { ...edit, bleep: subtractRange(bl, a - 0.02, b + 0.02), unbleep: mergeRanges([...un, [a, b]]) }
        : { ...edit, bleep: mergeRanges([...bl, [a, b]]), unbleep: subtractRange(un, a - 0.02, b + 0.02) },
    );
    setSel(null);
  };

  // Delete / Backspace cuts the selected words (while nothing else has the keyboard).
  useEffect(() => {
    if (!sel) return;
    const on = (e: KeyboardEvent) => {
      if (typing(e)) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        toggleSelection();
      } else if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        bleepSelection();
      } else if (e.key === "Escape") setSel(null);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  // Dragging: a word selection, or a trim handle.
  useEffect(() => {
    if (!drag) return;
    const indexAt = (x: number, y: number) => {
      const el = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-wi]");
      return el ? Number(el.dataset.wi) : null;
    };
    const move = (e: PointerEvent) => {
      const i = indexAt(e.clientX, e.clientY);
      if (i == null) return;
      if (drag.kind === "select") {
        if (i !== drag.anchor) setDrag({ ...drag, moved: true });
        setSel([drag.anchor, i]);
      } else setDrag({ ...drag, at: i });
    };
    const up = () => {
      if (drag.kind === "start") {
        const w = words[Math.min(drag.at, lastIn)];
        if (w && range.end - (w.start - 0.05) >= 1) onChange({ ...edit, start: Math.max(0, w.start - 0.05) });
      } else if (drag.kind === "end") {
        const w = words[Math.max(drag.at, firstIn)];
        if (w && w.end + 0.2 - range.start >= 1) onChange({ ...edit, end: w.end + 0.2 });
      }
      setDrag(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [drag]); // eslint-disable-line react-hooks/exhaustive-deps

  const lo = sel ? Math.min(sel[0], sel[1]) : -1;
  const hi = sel ? Math.max(sel[0], sel[1]) : -1;
  const startAt = drag?.kind === "start" ? drag.at : firstIn;
  const endAt = drag?.kind === "end" ? drag.at : lastIn;
  const playing = words.findIndex((w) => time >= w.start && time < w.end + 0.05);
  const edited = !!(edit && (edit.start != null || edit.end != null || edit.deleted?.length || edit.bleep?.length || edit.unbleep?.length));
  const outDur = plan?.duration ?? range.end - range.start;

  return (
    <section className="panel transcript" aria-labelledby="tx-title">
      <div className="panel-head">
        <h2 className="section-title" id="tx-title">
          {t("tx.title")}
        </h2>
        <div className="tx-tools">
          <span className="tc muted" title={t("tx.length_hint")}>
            {num(Math.round((range.end - range.start) * 10) / 10)} s
            {Math.abs(outDur - (range.end - range.start)) > 0.05 && <> → <b className="gold">{num(Math.round(outDur * 10) / 10)} s</b></>}
          </span>
          <button className="btn btn-sm btn-ghost" onClick={toggleSelection} disabled={!sel} title={`${t("tx.cut")} (Del)`}>
            <Icon name="x" />
            {t("tx.cut")}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={bleepSelection} disabled={!sel} title={`${t("tx.bleep_hint")} (B)`}>
            {t("tx.bleep")}
          </button>
          <button className="btn btn-sm btn-ghost icon-btn" onClick={onUndo} disabled={!canUndo} title={`${t("tx.undo")} (Ctrl+Z)`} aria-label={t("tx.undo")}>
            <Icon name="refresh" className="icon flip-x" />
          </button>
          <button className="btn btn-sm btn-ghost icon-btn" onClick={onRedo} disabled={!canRedo} title={`${t("tx.redo")} (Ctrl+Shift+Z)`} aria-label={t("tx.redo")}>
            <Icon name="refresh" />
          </button>
          {edited && (
            <button className="btn btn-sm btn-ghost" onClick={() => onChange({})}>
              {t("tx.reset")}
            </button>
          )}
        </div>
      </div>
      {words.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          {t("tx.empty")}
        </p>
      ) : (
        <div className={`tx-words${drag ? " dragging" : ""}`} ref={box} dir="auto" lang={lang ?? undefined}>
          {words.map((w, i) => {
            const del = isDeleted(w);
            const a = auto.get(i);
            const cls = [
              "tx-w",
              !(i >= startAt && i <= endAt) && "out",
              del && "del",
              a && !del && `auto-${a}`,
              bleeped.has(w.start.toFixed(2)) && !del && "bleep",
              maybe.has(w.start.toFixed(2)) && !del && "maybe",
              multi && w.spk && `spk-${w.spk}`,
              i >= lo && i <= hi && "sel",
              i === playing && "now",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <Fragment key={i}>
                {i === startAt && (
                  <span
                    className="tx-handle"
                    role="slider"
                    aria-label={t("tx.trim_start")}
                    aria-valuetext={fmtTime(range.start, true)}
                    title={t("tx.trim_hint")}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      setDrag({ kind: "start", at: startAt });
                    }}
                  >
                    [
                  </span>
                )}
                {multi && w.spk && (i === 0 || words[i - 1].spk !== w.spk) && (
                  <span className={`spk-chip spk-${w.spk}`}>{speakerLabel(w.spk, plan?.speakers, t)}</span>
                )}
                {gaps.get(i) != null && i > startAt && i <= endAt && (
                  <span className="tx-gap" title={t("tx.silence_cut")}>
                    ⋯ {num(Math.round(gaps.get(i)! * 10) / 10)} s
                  </span>
                )}
                <span
                  className={cls}
                  data-wi={i}
                  title={
                    a
                      ? t(`tx.auto_${a}`)
                      : bleeped.has(w.start.toFixed(2))
                        ? t("tx.bleeped")
                        : maybe.has(w.start.toFixed(2))
                          ? t("tx.maybe")
                          : fmtTime(w.start, true)
                  }
                  onPointerDown={(e) => {
                    if (e.button !== 0) return;
                    e.preventDefault();
                    if (e.shiftKey && sel) {
                      setSel([sel[0], i]);
                      return;
                    }
                    setSel([i, i]);
                    setDrag({ kind: "select", anchor: i, moved: false });
                  }}
                  onClick={() => {
                    if (drag?.kind === "select" && drag.moved) return;
                    onSeek(w.start);
                  }}
                >
                  {w.word}
                </span>
                {i === endAt && (
                  <span
                    className="tx-handle"
                    role="slider"
                    aria-label={t("tx.trim_end")}
                    aria-valuetext={fmtTime(range.end, true)}
                    title={t("tx.trim_hint")}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      setDrag({ kind: "end", at: endAt });
                    }}
                  >
                    ]
                  </span>
                )}
                {joiner}
              </Fragment>
            );
          })}
        </div>
      )}
      <p className="muted tx-help">{t("tx.help")}</p>
    </section>
  );
}
