import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Job } from "./api";

interface JobsState {
  jobs: Job[];
  connected: boolean;
  /** Increments whenever a job finishes (done/error/cancelled): pages refetch on it. */
  finishedTick: number;
  lastFinished: Job | null;
}

const Ctx = createContext<JobsState>({ jobs: [], connected: false, finishedTick: 0, lastFinished: null });

/** Live job list over Server-Sent Events (auto-reconnects). */
export function JobsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<JobsState>({ jobs: [], connected: false, finishedTick: 0, lastFinished: null });
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
        jobs,
        connected: true,
        finishedTick: s.finishedTick + tick,
        lastFinished: last ?? s.lastFinished,
      }));
    };

    const connect = () => {
      es = new EventSource("/api/events");
      es.addEventListener("jobs", (e) => apply(JSON.parse((e as MessageEvent).data)));
      es.onerror = () => {
        setState((s) => ({ ...s, connected: false }));
        es?.close();
        if (!closed) retry = window.setTimeout(connect, 2500);
      };
    };
    api.jobs().then((jobs) => {
      prev.current = new Map(jobs.map((j) => [j.id, j.status]));
    }).catch(() => {});
    connect();
    return () => {
      closed = true;
      es?.close();
      window.clearTimeout(retry);
    };
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useJobs = () => useContext(Ctx);

export const isActive = (j: Job) => j.status === "queued" || j.status === "running";
