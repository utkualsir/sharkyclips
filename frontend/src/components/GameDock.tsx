import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { Job } from "../api";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { go, href } from "../router";
import { useUiMode } from "../uimode";
import { BrandMark } from "./Brand";
import { jobLabel } from "./ui";

// 1.2.59: the waiting mini game. A small button at the bottom left while a project is being
// processed (Easy and Pro mode); the game itself (minigame/) loads only when it is opened, so it
// costs nothing otherwise. Settings can turn the button off; Settings also has "Play now".
const Panel = lazy(() => import("../minigame/Panel"));

/** Jobs that are not "your project is being made" (background upkeep): no game button for them. */
const BACKGROUND = new Set(["yt_stats", "reconcile", "pubqueue", "post", "hook_fetch", "update", "setup", "benchmark"]);
export const OPEN_EVENT = "sc-minigame-open";

export function openMiniGame(): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT));
}

const working = (j: Job) => isActive(j) && !!j.project_id && !BACKGROUND.has(j.kind);

export function GameDock() {
  const { t, num } = useI18n();
  const { settings } = useUiMode();
  const { jobs, finishedTick, lastFinished } = useJobs();
  const enabled = settings?.minigame !== false;
  const busy = jobs.filter(working);
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [ready, setReady] = useState<{ projectId: string; ok: boolean } | null>(null);
  // projects that were processing while the game was open: the toast is for them
  const watched = useRef<Set<string>>(new Set());
  const busyKey = busy.map((j) => j.project_id).join(",");

  useEffect(() => {
    const on = () => {
      setOpen(true);
      setLoaded(true);
    };
    window.addEventListener(OPEN_EVENT, on);
    return () => window.removeEventListener(OPEN_EVENT, on);
  }, []);

  useEffect(() => {
    if (open) for (const j of busy) if (j.project_id) watched.current.add(j.project_id);
  }, [open, busyKey]);

  useEffect(() => {
    const j = lastFinished;
    if (!j?.project_id || !watched.current.has(j.project_id)) return;
    if (jobs.some((x) => working(x) && x.project_id === j.project_id)) return; // more steps to come
    watched.current.delete(j.project_id);
    setReady({ projectId: j.project_id, ok: j.status === "done" });
  }, [finishedTick]);

  if (!enabled && !open) return null;
  const showButton = enabled && !open && (busy.length > 0 || ready !== null);
  const job = busy.find((j) => j.status === "running") ?? busy[0] ?? null;
  const progress = job ? { label: jobLabel(job, t, num), pct: job.progress } : null;

  return (
    <>
      {showButton && (
        <button
          type="button"
          className={`mg-dock${ready ? " mg-dock-ready" : ""}`}
          onClick={() => {
            if (ready && !busy.length) {
              // the game is closed and the clips are done: this button goes to them
              setReady(null);
              go(href.project(ready.projectId));
              return;
            }
            setLoaded(true);
            setOpen(true);
          }}
          title={ready && !busy.length ? undefined : t("mg.open_hint")}
        >
          <span className="mg-dock-mark" aria-hidden="true">
            <BrandMark size={18} />
          </span>
          <span>{ready && !busy.length ? (ready.ok ? t("mg.ready_open") : t("mg.failed_open")) : t("mg.open")}</span>
        </button>
      )}
      {loaded && (
        <Suspense fallback={null}>
          <Panel
            open={open}
            progress={progress}
            ready={ready}
            onClose={() => setOpen(false)}
            onReadySeen={() => setReady(null)}
          />
        </Suspense>
      )}
    </>
  );
}
