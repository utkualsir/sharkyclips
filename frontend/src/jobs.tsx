import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type GovernorView, type Job, type ResourceSample, type ShutdownState } from "./api";

interface JobsState {
  jobs: Job[];
  connected: boolean;
  /** Increments whenever a job finishes (done/error/cancelled): pages refetch on it. */
  finishedTick: number;
  lastFinished: Job | null;
  shutdown: ShutdownState | null;
  /** performance.now() when `shutdown` arrived (the countdown runs locally from there) */
  shutdownAt: number;
  /** resource governor: mode, state and the latest resource sample (every ~2 s) */
  governor: GovernorView | null;
  /** last 5 minutes of resource samples, oldest first */
  history: ResourceSample[];
}

const HISTORY = 150;
const EMPTY: JobsState = {
  jobs: [], connected: false, finishedTick: 0, lastFinished: null, shutdown: null, shutdownAt: 0,
  governor: null, history: [],
};
const Ctx = createContext<JobsState>(EMPTY);

/** Live job list over Server-Sent Events (auto-reconnects). */
export function JobsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<JobsState>(EMPTY);
  const prev = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;
    let retry: number | undefined;

    const apply = (jobs: Job[]) => {
      let tick = 0;
      let last: Job | null = null;
      for (const j of jobs) {
        const before = prev.current.get(j.id);
        const ended = j.status === "done" || j.status === "error" || j.status === "cancelled";
        if (ended && before && before !== j.status) {
          tick++;
          last = j;
        }
      }
      prev.current = new Map(jobs.map((j) => [j.id, j.status]));
      setState((s) => ({
        ...s,
        jobs,
        connected: true,
        finishedTick: s.finishedTick + tick,
        lastFinished: last ?? s.lastFinished,
      }));
    };

    const connect = () => {
      es = new EventSource("/api/events");
      es.addEventListener("jobs", (e) => apply(JSON.parse((e as MessageEvent).data)));
      es.addEventListener("shutdown", (e) =>
        setState((s) => ({ ...s, shutdown: JSON.parse((e as MessageEvent).data), shutdownAt: performance.now() })),
      );
      es.addEventListener("governor", (e) => {
        const g = JSON.parse((e as MessageEvent).data) as GovernorView;
        setState((s) => {
          const last = s.history[s.history.length - 1];
          const add = g.sample && (!last || g.sample.t > last.t) ? [{ ...g.sample, state: g.state }] : [];
          return { ...s, governor: g, history: add.length ? [...s.history, ...add].slice(-HISTORY) : s.history };
        });
      });
      es.onerror = () => {
        setState((s) => ({ ...s, connected: false }));
        es?.close();
        if (!closed) retry = window.setTimeout(connect, 2500);
      };
    };
    api.jobs().then((jobs) => {
      prev.current = new Map(jobs.map((j) => [j.id, j.status]));
    }).catch(() => {});
    api.governor(true).then((g) => {
      const hist = (g.history ?? []).slice(-HISTORY);
      setState((s) => ({ ...s, governor: s.governor ?? g, history: s.history.length > hist.length ? s.history : hist }));
    }).catch(() => {});
    connect();
    const beat = () => {
      if (document.visibilityState === "visible") api.watchGovernor().catch(() => {});
    };
    const heartbeat = window.setInterval(beat, 5000);
    document.addEventListener("visibilitychange", beat);
    return () => {
      window.clearInterval(heartbeat);
      document.removeEventListener("visibilitychange", beat);
      closed = true;
      es?.close();
      window.clearTimeout(retry);
    };
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useJobs = () => useContext(Ctx);

export const isActive = (j: Job) => j.status === "queued" || j.status === "running";
