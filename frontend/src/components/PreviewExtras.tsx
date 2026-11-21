import { useEffect, useRef, useState } from "react";
import { ClipVideo } from "./ClipEnd";
import { api, urls, type ClipOptions, type EditPlanView, type FinalPreviewState } from "../api";
import { useJobs } from "../jobs";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Modal, ProgressBar, Segmented } from "./ui";

// 1.2.45: the preview shows what goes to the platforms. PlatformOverlay draws the platform's own
// buttons / title area (export.PRESETS safe zones, from the plan) over the 9:16 preview;
// FinalPreview renders the real file small (render_clip, the same as the export) and plays it.

export type PlatformView = "none" | "shorts" | "tiktok" | "reels";
const CW = 1080;
const CH = 1920;

export function PlatformTabs({ value, onChange }: { value: PlatformView; onChange: (v: PlatformView) => void }) {
  const { t } = useI18n();
  return (
    <Segmented<PlatformView>
      value={value}
      onChange={onChange}
      label={t("pview.label")}
      options={[
        { value: "none", label: t("pview.none") },
        { value: "shorts", label: "Shorts" },
        { value: "tiktok", label: "TikTok" },
        { value: "reels", label: "Reels" },
      ]}
    />
  );
}

/** Half-transparent platform UI over the preview: top bar, the button column, the title /
 * description area. Captions and texts that sit under it would be hidden on the phone. */
export function PlatformOverlay({ plan, view }: { plan: EditPlanView | null; view: PlatformView }) {
  const { t } = useI18n();
  if (view === "none" || !plan?.safe_zones) return null;
  const [top, right, bottom, left] = plan.safe_zones[view];
  const pct = (v: number, of: number) => `${(v / of) * 100}%`;
  const name = view === "shorts" ? "YouTube Shorts" : view === "tiktok" ? "TikTok" : "Instagram Reels";
  return (
    <div className={`pview pview-${view}`} aria-label={t("pview.overlay", { p: name })} role="img">
      <div className="pview-top" style={{ height: pct(top, CH) }}>
        <span>{t("pview.top")}</span>
      </div>
      <div className="pview-right" style={{ top: pct(top, CH), bottom: pct(bottom, CH), width: pct(right, CW) }}>
        {[0, 1, 2, 3].map((i) => (
          <i key={i} />
        ))}
      </div>
      {left > 0 && <div className="pview-left" style={{ top: pct(top, CH), bottom: pct(bottom, CH), width: pct(left, CW) }} />}
      <div className="pview-bottom" style={{ height: pct(bottom, CH) }}>
        <b>@yourchannel</b>
        <span>{t("pview.caption")}</span>
        <em>{t("pview.bottom")}</em>
      </div>
    </div>
  );
}

/** "Final preview": the platform file, rendered small, played here. */
export function FinalPreview({
  projectId,
  cid,
  options,
  hook,
  disabled,
}: {
  projectId: string;
  cid: string | null;
  options: ClipOptions;
  hook: string;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const { jobs } = useJobs();
  const [open, setOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [state, setState] = useState<FinalPreviewState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const job = jobs.find((j) => j.id === jobId) ?? null;
  const done = useRef<string | null>(null);

  useEffect(() => {
    setJobId(null);
    setState(null);
    setErr(null);
  }, [cid]);

  useEffect(() => {
    if (!job || !cid) return;
    if (job.status === "done" && done.current !== job.id) {
      done.current = job.id;
      api.finalPreviewState(projectId, cid).then(setState).catch(() => setState(null));
    }
    if (job.status === "error") setErr(job.error?.message ?? t("final.failed"));
  }, [job?.status, job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = () => {
    if (!cid) return;
    setOpen(true);
    setErr(null);
    setState(null);
    api
      .finalPreview(projectId, cid, { options, hook })
      .then((r) => setJobId(r.job.id))
      .catch((e: Error) => setErr(e.message));
  };
  const busy = !!job && (job.status === "queued" || job.status === "running");

  return (
    <>
      <button className="btn btn-sm" onClick={start} disabled={disabled || !cid || busy} title={t("final.hint")}>
        {busy ? <span className="spinner" /> : <Icon name="film" />}
        {t("final.button")}
      </button>
      {open && (
        <Modal title={t("final.title")} onClose={() => setOpen(false)}>
          <p className="muted small" style={{ marginTop: 0 }}>
            {t("final.explain")}
          </p>
          {err && (
            <p className="swear-warn small" role="alert">
              {err}
            </p>
          )}
          {!err && !state?.ready && (
            <div className="final-wait">
              <span>{job?.stage ? t(`stage.${job.stage}`) : t("final.making")}</span>
              <ProgressBar value={job?.progress ?? null} label={t("final.making")} />
            </div>
          )}
          {state?.ready && cid && (
            <div className="final-play">
              <ClipVideo src={urls.finalPreview(projectId, cid, state.at ?? "")} autoPlay compact={false} label={t("final.title")} />
              <p className="muted small">
                {t("final.bleeps", { n: state.bleeps?.length ?? 0 })}
              </p>
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
