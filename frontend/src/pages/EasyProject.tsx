// Easy mode, 1.2.68: three steps only. 1 the video was dropped in (Home) -> 2 the Shorts appear in
// one big grid, all at once -> 3 tick YouTube / Instagram / TikTok and press Share. Notices say per
// clip "Shared to YouTube ✓" (with the link) or what went wrong. Everything else is in Pro mode.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, easyApi, type EasyView } from "../api";
import { EasyProgress } from "../components/Easy";
import { Icon } from "../components/Icons";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { href } from "../router";
import { shareChanged } from "../share";
import { ShareBoardView } from "./ShareClips";

export default function EasyProject({ id }: { id: string }) {
  const { t } = useI18n();
  const { finishedTick } = useJobs();
  const [view, setView] = useState<EasyView | null>(null);
  const [missing, setMissing] = useState(false);
  const prepared = useRef(false);

  const load = useCallback(async () => {
    try {
      // the first call starts what the clips still need (renders); later ones only read
      const v = prepared.current ? await easyApi.view(id) : await easyApi.prepare(id);
      prepared.current = true;
      setView(v);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setMissing(true);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load, finishedTick]);
  const working = view?.state === "working";
  const nClips = view?.clips.length ?? 0;
  useEffect(() => {
    if (nClips) shareChanged(); // new Shorts are ready: the board shows them at once
  }, [nClips]);
  useEffect(() => {
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), working ? 2000 : 20000);
    return () => window.clearInterval(iv);
  }, [working, load]);

  if (missing) {
    return (
      <main className="page ez-page">
        <div className="empty">
          <Icon name="film" size={30} />
          <h1 className="display">{t("easy.missing")}</h1>
          <a className="btn btn-primary btn-lg" href={href.library}>
            {t("easy.new_video")}
          </a>
        </div>
      </main>
    );
  }
  if (!view) {
    return (
      <main className="page ez-page" aria-busy="true">
        <div className="skeleton" style={{ height: 40, width: "50%", marginBottom: 24 }} />
        <div className="ez-grid">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton ez-card-skel" />
          ))}
        </div>
      </main>
    );
  }

  const hasClips = view.clips.length > 0;
  return (
    <main className="page ez-page share-page">
      <a className="ez-back" href={href.library}>
        <Icon name="chevron-left" size={16} className="flip-rtl" /> {t("easy.new_video")}
      </a>
      {!hasClips && (
        <div className="ez-head">
          <div className="ez-head-text">
            <h1 className="ez-title" dir="auto">
              {view.title}
            </h1>
          </div>
        </div>
      )}
      {working && <EasyProgress steps={view.steps} eta={view.eta_seconds} compact={hasClips} />}
      {working && view.pc?.slow && <SlowPcNote light={view.pc.light} />}
      {view.state === "error" && view.error && (
        <div className="notice notice-danger ez-error" role="alert">
          <Icon name="alert" />
          <div style={{ flex: 1 }}>
            <div className="notice-title">{t("easy.failed")}</div>
            <div className="muted">{view.error.message}</div>
          </div>
          <button
            className="btn"
            onClick={() =>
              easyApi
                .retry(id)
                .then(setView)
                .catch(() => {})
            }
          >
            {t("common.retry")}
          </button>
        </div>
      )}
      {view.state === "empty" && !working && (
        <div className="empty">
          <Icon name="sparkles" size={30} />
          <h2 className="display">{t("easy.no_clips")}</h2>
          <p style={{ maxWidth: "46ch", margin: 0 }}>{t("easy.no_clips_body")}</p>
        </div>
      )}
      {hasClips && <ShareBoardView id={id} easy />}
    </main>
  );
}

function SlowPcNote({ light }: { light: boolean }) {
  const { t } = useI18n();
  const [on, setOn] = useState(light);
  const [busy, setBusy] = useState(false);
  return (
    <div className={`notice perf-note${on ? "" : " notice-warn"}`} role="status" style={{ marginTop: 12 }}>
      <span>
        {t("perf.slow_pc")} {on && t("perf.slow_pc_light")}
      </span>
      {!on && (
        <button
          className="btn btn-sm"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            api
              .saveSettings({ performance_preset: "light" })
              .then(() => setOn(true))
              .catch(() => {})
              .finally(() => setBusy(false));
          }}
        >
          {busy && <span className="spinner" />} {t("perf.use_light")}
        </button>
      )}
    </div>
  );
}
