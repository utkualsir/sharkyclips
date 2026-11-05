// Cover studio (1.2.18): four AI cover pictures made on this PC, one click to choose.
import { useEffect, useState } from "react";
import { api } from "../api";
import { coversApi, coverUrls, type AiCoversView, type CoverFrame } from "../extras";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { JobLine } from "./ui";

export function useAiCovers(pid: string, cid: string) {
  const { jobs, finishedTick } = useJobs();
  const [view, setView] = useState<AiCoversView | null>(null);
  const job = jobs.find((j) => j.kind === "ai_cover" && j.project_id === pid && j.params?.clip_id === cid && isActive(j)) ?? null;
  useEffect(() => {
    coversApi.view(pid, cid).then(setView).catch(() => {});
  }, [pid, cid, finishedTick]);
  return { view, setView, job };
}

/** The honest one-liner: where the pictures are made, or why the facecam frame is used. */
export function CoverAiNote({ view }: { view: AiCoversView }) {
  const { t, num } = useI18n();
  const p = view.plan;
  if (p.use === "fallback") {
    return (
      <p className="field-hint" role="note">
        <Icon name="camera" size={12} /> {t(`cover_ai.fallback.${p.capability.reason}`)} {t("cover_ai.fallback_face")}
      </p>
    );
  }
  const left = Math.max(0, p.download_bytes - p.downloaded_bytes);
  return (
    <p className="field-hint">
      <Icon name="sparkles" size={12} /> {t(p.use === "gpu" ? "cover_ai.on_gpu" : "cover_ai.on_cpu", { m: num(p.minutes_per_picture ?? 0) })}
      {!p.model_ready && <> · {t("cover_ai.first_download", { size: fmtBytes(left) })}</>}
    </p>
  );
}

export function CoverStudio({
  pid,
  cid,
  frames,
  text,
  lang,
  onChosen,
  compact,
}: {
  pid: string;
  cid: string;
  /** sizes to make; the picker shows the first one */
  frames: CoverFrame[];
  text: string;
  lang: string | null;
  onChosen?: (frame: CoverFrame, seed: number) => void;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const { view, setView, job } = useAiCovers(pid, cid);
  const [frame, setFrame] = useState<CoverFrame>(frames[0]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setFrame(frames[0]), [frames.join()]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!view) return <div className="skeleton" style={{ height: 40 }} />;
  const opts = view.options[frame] ?? [];
  const make = async (fresh: boolean) => {
    setBusy(true);
    try {
      await coversApi.make(pid, cid, frames, fresh);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const choose = async (seed: number) => {
    try {
      setView(await coversApi.choose(pid, cid, frame, seed));
      onChosen?.(frame, seed);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const stamp = view.made_at ?? "";

  return (
    <div className="cover-studio">
      {job ? (
        <JobLine job={job} onCancel={() => api.cancelJob(job.id).catch(() => {})} />
      ) : view.plan.use === "fallback" ? null : opts.length === 0 ? (
        <button type="button" className={`btn${compact ? " ez-big" : " btn-sm"} btn-primary`} disabled={busy} onClick={() => make(true)}>
          <Icon name="sparkles" /> {t("cover_ai.make")}
        </button>
      ) : null}
      {opts.length > 0 && (
        <>
          {frames.length > 1 && (
            <div className="segmented" role="group" aria-label={t("cover_ai.size")}>
              {frames.map((f) => (
                <button key={f} type="button" aria-pressed={f === frame} onClick={() => setFrame(f)}>
                  {t(`cover_ai.frame.${f}`)}
                </button>
              ))}
            </div>
          )}
          <div className={`cover-ai-grid${frame === "wide" ? " wide" : ""}`} role="radiogroup" aria-label={t("cover_ai.pick")}>
            {opts.map((seed, i) => {
              const on = view.chosen[frame] === seed;
              return (
                <label key={seed} className={`cover-opt${on ? " on" : ""}`}>
                  <input type="radio" name={`ai-cover-${cid}-${frame}`} checked={on} onChange={() => choose(seed)} />
                  <span className="cover-img">
                    <img src={coverUrls.option(pid, cid, seed, frame, text, lang, stamp)} alt={t("cover_ai.option", { n: i + 1 })} loading="lazy" />
                  </span>
                </label>
              );
            })}
          </div>
          {!job && (
            <button type="button" className="link-btn field-hint" disabled={busy} onClick={() => make(true)}>
              <Icon name="refresh" size={12} /> {t("cover_ai.again")}
            </button>
          )}
        </>
      )}
      <CoverAiNote view={view} />
    </div>
  );
}
