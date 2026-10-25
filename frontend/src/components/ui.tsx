import { useEffect, useRef, useState, type ReactNode } from "react";
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

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className="toggle"
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
    />
  );
}

export function ProgressBar({ value }: { value: number | null | undefined }) {
  const indet = value == null;
  return (
    <div
      className={`progress${indet ? " indeterminate" : ""}`}
      role="progressbar"
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
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const on = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", on);
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("input, textarea, button:not(.modal-x)")?.focus();
    return () => {
      window.removeEventListener("keydown", on);
      prev?.focus?.();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? " modal-wide" : ""}`} role="dialog" aria-modal="true" ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
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
  return job.status === "running" && job.paused ? `${t("job.paused")} · ${base}` : base;
}

function jobBaseLabel(job: Job, t: ReturnType<typeof useI18n>["t"], num: (n: number) => string): string {
  if (job.status === "queued") return job.lane === "gpu" ? t("job.waiting") : t("status.queued");
  if (job.kind === "analyze" && job.detail?.count) {
    return `${t("stage.llm_analyzing")} ${job.detail.index}/${job.detail.count}`;
  }
  if (job.kind === "render" && (job.params?.batch_count ?? 0) > 1) {
    const base = t("render.progress", { i: job.params.batch_index, n: job.params.batch_count });
    return job.progress != null ? `${base} · ${num(Math.round(job.progress * 100))}%` : base;
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
