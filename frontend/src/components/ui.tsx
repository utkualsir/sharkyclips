import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Job } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  block,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  block?: boolean;
  label?: string;
}) {
  return (
    <div className={`segmented${block ? " block" : ""}`} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Scroll to an element, opening any folded "Advanced" section around it first (1.2.63). */
export function revealById(id: string, opts: ScrollIntoViewOptions = { block: "start" }) {
  const el = document.getElementById(id);
  if (!el) return;
  for (let d = el.closest("details"); d; d = d.parentElement?.closest("details") ?? null) d.open = true;
  el.scrollIntoView(opts);
}

/** 1.2.63 Pro mode: the less used controls of a screen, folded away (one look on every screen). */
export function Advanced({
  label,
  children,
  className = "",
  id,
  hint,
}: {
  label: string;
  children: ReactNode;
  className?: string;
  id?: string;
  hint?: string;
}) {
  return (
    <details className={`advanced ${className}`.trim()} id={id}>
      <summary>
        <span className="advanced-chev" aria-hidden="true" />
        {label}
      </summary>
      <div className="advanced-body">
        {hint && <p className="field-hint advanced-hint">{hint}</p>}
        {children}
      </div>
    </details>
  );
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className="toggle"
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
    />
  );
}

export function ProgressBar({ value, label }: { value: number | null | undefined; label?: string }) {
  const { t } = useI18n();
  const indet = value == null;
  return (
    <div
      className={`progress${indet ? " indeterminate" : ""}`}
      role="progressbar"
      aria-label={label ?? t("common.progress")}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indet ? undefined : Math.round(value * 100)}
    >
      <span style={{ width: indet ? undefined : `${Math.max(2, value * 100)}%` }} />
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
  top,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  /** above other open dialogs (a question asked while a dialog is open) */
  top?: boolean;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  // Issue #5: callers often pass an inline onClose and their parent re-renders on every poll.
  // The old effect depended on onClose, so it re-ran on every render: it moved the focus to the
  // first field (Backspace in the title box went to a radio button) and scrolled the dialog back
  // to the top. Now the focus is set ONCE when the dialog opens, without scrolling.
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const dialogs = document.querySelectorAll('[aria-modal="true"]');
      if (dialogs.length && dialogs[dialogs.length - 1] !== ref.current) return; // only the top dialog closes
      e.stopPropagation();
      close.current();
    };
    window.addEventListener("keydown", on);
    const prev = document.activeElement as HTMLElement | null;
    const first =
      ref.current?.querySelector<HTMLElement>("[autofocus], [data-autofocus]") ??
      ref.current?.querySelector<HTMLElement>(
        'input:not([type="radio"]):not([type="checkbox"]):not([type="range"]):not([disabled]), textarea:not([disabled]), button:not(.modal-x):not([disabled])',
      );
    first?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener("keydown", on);
      if (prev && document.contains(prev)) prev.focus?.({ preventScroll: true });
    };
  }, []);
  return (
    <div className={`modal-backdrop${top ? " modal-top" : ""}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? " modal-wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button className="btn btn-ghost icon-btn modal-x" onClick={onClose} aria-label={t("common.close")}>
            <Icon name="x" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function CopyButton({ text, label, small = true }: { text: string; label?: string; small?: boolean }) {
  const { t } = useI18n();
  const toast = useToast();
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // http on a LAN address: the async clipboard API needs a secure context
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setDone(true);
    toast({ kind: "ok", text: t("common.copied") });
    window.setTimeout(() => setDone(false), 1500);
  };
  return (
    <button
      type="button"
      className={`btn ${small ? "btn-sm" : ""} ${label ? "" : "icon-btn"} btn-ghost`}
      onClick={copy}
      aria-label={label ?? t("common.copy")}
      title={label ?? t("common.copy")}
    >
      <Icon name={done ? "check" : "copy"} />
      {label}
    </button>
  );
}

/** "Transcribing 60%", "Waiting for the GPU", ... */
export function jobLabel(job: Job, t: ReturnType<typeof useI18n>["t"], num: (n: number) => string): string {
  const base = jobBaseLabel(job, t, num);
  return job.status === "running" && job.paused ? `${t("job.paused")}, ${base}` : base;
}

function jobBaseLabel(job: Job, t: ReturnType<typeof useI18n>["t"], num: (n: number) => string): string {
  if (job.status === "queued") return job.lane === "gpu" ? t("job.waiting") : t("status.queued");
  if (job.kind === "analyze" && job.detail?.count) {
    return `${t("stage.llm_analyzing")} ${job.detail.index}/${job.detail.count}`;
  }
  if (job.kind === "render" && (job.params?.batch_count ?? 0) > 1) {
    const base = t("render.progress", { i: job.params.batch_index, n: job.params.batch_count });
    return job.progress != null ? `${base}, ${num(Math.round(job.progress * 100))}%` : base;
  }
  const stage = job.stage ? t(`stage.${job.stage}`) : t(`kind.${job.kind}`);
  return job.progress != null && job.progress > 0 ? `${stage} ${num(Math.round(job.progress * 100))}%` : stage;
}

export function JobLine({ job, onCancel }: { job: Job; onCancel?: () => void }) {
  const { t, num } = useI18n();
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <span className="status status-running">
          <span className="dot" />
          {jobLabel(job, t, num)}
        </span>
        {onCancel && (
          <button className="btn btn-sm btn-ghost" onClick={onCancel}>
            {t("job.cancel")}
          </button>
        )}
      </div>
      <ProgressBar value={job.status === "queued" ? null : job.progress} />
    </div>
  );
}

/** Separator between short facts on one line ("Kick | Live now"): a thin rule, not a middle dot.
 *  Screen readers hear a comma. */
export function Sep() {
  return (
    <span className="sep">
      <span className="visually-hidden">, </span>
    </span>
  );
}
