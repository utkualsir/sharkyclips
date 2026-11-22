import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type Job, type SetupItem, type SetupPlan } from "../api";
import { useAppState } from "../appstate";
import { fmtBytes, fmtEta } from "../format";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useMeta } from "../meta";
import { Icon } from "./Icons";
import { ProgressBar, revealById, Sep } from "./ui";

const MB = 1024 * 1024;

/** 1.2.56 first-run downloads: what this PC needs (picked for its hardware), sizes, then one
 * download with a progress bar, speed and time left. Used in the onboarding ("welcome" look),
 * in Settings > Downloads and behind the "still needs its AI parts" banner. */
export function SetupDownloads({ look = "card", onReady }: { look?: "welcome" | "card"; onReady?: () => void }) {
  const { t, num } = useI18n();
  const meta = useMeta();
  const { jobs } = useJobs();
  const { refresh } = useAppState();
  const [plan, setPlan] = useState<SetupPlan | null>(null);
  const [failed, setFailed] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .setupPlan()
      .then((p) => {
        setPlan(p);
        setPicked(new Set(p.items.filter((i) => i.selected).map((i) => i.id)));
        if (p.job) setJobId(p.job.id);
      })
      .catch(() => setFailed(true));
  }, []);
  useEffect(load, [load]);

  const job: Job | undefined = jobs.find((j) => j.kind === "setup" && (j.id === jobId || isActive(j)));
  const running = !!job && isActive(job);
  const finished = job && !isActive(job) && job.id === jobId ? job : null;

  useEffect(() => {
    if (!finished) return;
    load();
    refresh?.();
    if (finished.status === "done" && finished.result?.ok) onReady?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished?.id, finished?.status]);

  const todo = useMemo(() => (plan ? plan.items.filter((i) => i.available && !i.present) : []), [plan]);
  const totalMb = todo.filter((i) => picked.has(i.id)).reduce((s, i) => s + i.size_mb, 0);
  const noSpace = plan?.free_mb != null && totalMb > plan.free_mb - 1024;

  const start = () => {
    setError(null);
    const ids = todo.filter((i) => picked.has(i.id)).map((i) => i.id);
    api
      .setupDownload(ids)
      .then((j) => setJobId(j.id))
      .catch((e) => setError(e.message));
  };

  const toggle = (it: SetupItem) => {
    if (!it.optional || running) return;
    setPicked((cur) => {
      const n = new Set(cur);
      if (n.has(it.id)) {
        n.delete(it.id);
        if (it.id === "ollama") n.delete("llm");
      } else {
        n.add(it.id);
        if (it.id === "llm" && todo.some((x) => x.id === "ollama")) n.add("ollama");
      }
      return n;
    });
  };

  const cls = look === "welcome" ? "setup setup-welcome" : "setup";
  if (failed) return <p className="muted">{t("setup.load_failed")}</p>;
  if (!plan)
    return (
      <p className="muted" aria-busy="true">
        <span className="spinner" style={{ width: 12, height: 12 }} /> {t("setup.loading")}
      </p>
    );

  const d = (job?.detail ?? {}) as {
    done_bytes?: number;
    total_bytes?: number;
    speed_bps?: number;
    eta_s?: number | null;
    items?: { id: string; status: string; done: number; total: number }[];
  };
  const itemState = (id: string) => d.items?.find((x) => x.id === id);
  const results: Record<string, { ok: boolean; error?: string }> = finished?.result?.results ?? {};
  const failedIds = Object.entries(results)
    .filter(([, r]) => !r.ok)
    .map(([id]) => id);

  const pcLine = plan.light ? t("setup.pc_light") : plan.device === "gpu" && plan.machine.gpu ? t("setup.pc_gpu", { gpu: plan.machine.gpu }) : t("setup.pc_cpu");

  return (
    <div className={cls}>
      <p className="setup-pc">
        <Icon name={plan.device === "gpu" ? "zap" : "clock"} size={16} />
        <span>{pcLine}</span>
      </p>
      <ul className="setup-list">
        {plan.items
          .filter((i) => i.available || i.present)
          .map((it) => {
            const st = itemState(it.id);
            const on = it.present || picked.has(it.id);
            const label = t(`setup.item.${it.id}`, { model: String(it.detail.model ?? "") });
            return (
              <li key={it.id} className={`setup-item${it.present ? " present" : ""}`}>
                <label className="setup-check">
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={it.present || !it.optional || running}
                    onChange={() => toggle(it)}
                    aria-describedby={`setup-${it.id}-desc`}
                  />
                  <span className="setup-name">
                    <b>{label}</b>
                    <span id={`setup-${it.id}-desc`} className="muted">
                      {t(`setup.item.${it.id}_desc`)}
                    </span>
                  </span>
                </label>
                <span className="setup-size">
                  {it.present ? (
                    <span className="setup-ok">
                      <Icon name="check" size={14} /> {t("setup.present")}
                    </span>
                  ) : st && (running || finished) ? (
                    <span className={`setup-st st-${st.status}`}>{t(`setup.status.${st.status}`)}</span>
                  ) : (
                    <>
                      {fmtBytes(it.size_mb * MB)}
                      {it.optional && <span className="chip">{t("setup.optional")}</span>}
                    </>
                  )}
                </span>
              </li>
            );
          })}
      </ul>

      {running && job ? (
        <div className="setup-progress" role="status" aria-live="polite">
          <ProgressBar value={job.status === "queued" ? null : job.progress} />
          <div className="setup-progress-line">
            <span>
              {d.total_bytes ? `${fmtBytes(d.done_bytes ?? 0)} / ${fmtBytes(d.total_bytes)}` : t("setup.status.waiting")}
              {d.speed_bps ? `, ${t("setup.speed", { speed: fmtBytes(d.speed_bps) })}` : ""}
            </span>
            <span>{d.eta_s != null ? t("setup.time_left", { time: fmtEta(d.eta_s, num, t) }) : ""}</span>
          </div>
          <div>
            <button className="btn btn-sm btn-ghost" onClick={() => api.cancelJob(job.id)}>
              {t("setup.cancel")}
            </button>
          </div>
        </div>
      ) : todo.length === 0 ? (
        <p className="setup-done" role="status">
          <Icon name="check" size={16} /> {t("setup.done")}
        </p>
      ) : (
        <div className="setup-actions">
          {failedIds.length > 0 && (
            <p className="notice notice-warn" role="alert">
              {t("setup.failed", { items: failedIds.map((id) => t(`setup.item.${id}`, { model: "" }).replace(/\s*\(\)\s*$/, "")).join(", ") })}
            </p>
          )}
          {error && (
            <p className="notice notice-warn" role="alert">
              {error}
            </p>
          )}
          <p className="setup-total">
            <b>{t("setup.total", { size: fmtBytes(totalMb * MB) })}</b>
            {plan.free_mb != null && <span className="muted"><Sep />{t("setup.free", { size: fmtBytes(plan.free_mb * MB) })}</span>}
          </p>
          {noSpace && <p className="notice notice-warn">{t("setup.no_space")}</p>}
          <p className="muted setup-offline">{t("setup.offline")}</p>
          <div>
            <button className="btn btn-primary btn-sm" onClick={start} disabled={!meta?.is_local || totalMb === 0}>
              <Icon name="download" />
              {failedIds.length ? t("setup.retry") : t("setup.download")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Settings > Downloads */
export function SetupCard() {
  const { t } = useI18n();
  useEffect(() => {
    // the banner links to #/settings/downloads
    if (window.location.hash.endsWith("/downloads"))
      window.setTimeout(() => revealById("downloads"), 50);
  }, []);
  return (
    <section className="card setting" id="downloads">
      <div>
        <h2>{t("setup.settings_title")}</h2>
        <p>{t("setup.settings_desc")}</p>
      </div>
      <SetupDownloads />
    </section>
  );
}

/** An installed copy that still misses its required parts (the onboarding was skipped, or a
 * download failed): one slim banner on every screen, opening Settings > Downloads. */
export function SetupBanner() {
  const { t } = useI18n();
  const { state } = useAppState();
  if (!state?.setup_needed || state.onboarding) return null;
  return (
    <div className="notice setup-banner" role="status">
      <Icon name="download" size={16} />
      <span>{t("setup.banner")}</span>
      <a className="btn btn-sm btn-primary" href="#/settings/downloads">
        {t("setup.banner_open")}
      </a>
    </div>
  );
}
