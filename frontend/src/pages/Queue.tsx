import { useEffect, useMemo, useRef, useState } from "react";
import { api, type AcceptedOverview, type Job, type ProjectSummary, type QueueView } from "../api";
import { Icon } from "../components/Icons";
import { jobLabel, ProgressBar, Toggle } from "../components/ui";
import { fmtEta } from "../format";
import { useI18n, type T } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";

const KIND_ICON: Record<string, string> = {
  render: "film",
  montage: "layers",
  import: "download",
  transcribe: "message",
  highlights: "sparkles",
  analyze: "sparkles",
  titles: "sparkles",
  benchmark: "clock",
  facecam: "camera",
  proxy: "film",
  chat: "hash",
  export: "download",
  upload: "upload",
  yt_stats: "chart",
};

function jobTitle(job: Job, t: T, projects: Map<string, string>): { title: string; sub: string | null } {
  const p = job.params ?? {};
  const projectTitle = p.project_title ?? (job.project_id ? projects.get(job.project_id) ?? job.project_id : null);
  if (job.kind === "export" || job.kind === "upload") {
    return { title: `#${String(p.rank ?? "?").padStart(2, "0")} · ${p.title || t(`kind.${job.kind}`)}`, sub: `${t(`kind.${job.kind}`)} · ${projectTitle ?? ""}` };
  }
  if (job.kind === "render") {
    return { title: `#${String(p.rank ?? "?").padStart(2, "0")} · ${p.title || t("kind.render")}`, sub: projectTitle };
  }
  if (job.kind === "montage") return { title: t("queue.montage_title", { n: p.count ?? 0 }), sub: projectTitle };
  if (job.kind === "import") return { title: t("kind.import"), sub: p.title ?? null };
  return { title: t(`kind.${job.kind}`), sub: projectTitle };
}

function openLink(job: Job): string | null {
  if (job.kind === "montage" && job.project_id) return href.bestof(job.project_id);
  if (job.kind === "benchmark") return href.settings;
  return job.project_id ? href.project(job.project_id) : null;
}

// ------------------------------------------------------------------ rows

function QueueRow({
  job,
  pos,
  queuedCount,
  projects,
  onMove,
  dragProps,
  dragOver,
}: {
  job: Job;
  pos: number;
  queuedCount: number;
  projects: Map<string, string>;
  onMove: (to: number) => void;
  dragProps: Record<string, any>;
  dragOver: boolean;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const running = job.status === "running";
  const { title, sub } = jobTitle(job, t, projects);
  const link = openLink(job);
  const cancel = () => api.cancelJob(job.id).catch((e) => toast({ kind: "err", text: e.message }));
  return (
    <li
      className={`q-row${running ? " running" : ""}${dragOver ? " drag-over" : ""}`}
      data-job={job.id}
      {...(running ? {} : dragProps)}
    >
      <span className="q-grip" aria-hidden="true">
        {running ? (
          job.paused ? <Icon name="pause" size={14} /> : <span className="spinner" style={{ width: 14, height: 14 }} />
        ) : (
          <span className="mono">{pos}</span>
        )}
      </span>
      <span className="q-icon" aria-hidden="true">
        <Icon name={KIND_ICON[job.kind] ?? "clock"} size={15} />
      </span>
      <div className="q-main">
        <div className="q-title" dir="auto">
          {link ? <a href={link}>{title}</a> : title}
          {job.detail?.resumed && <span className="chip chip-outline q-tag">{t("queue.resumed")}</span>}
          {(job.attempt ?? 1) > 1 && <span className="chip chip-outline q-tag">{t("queue.attempt", { n: job.attempt! })}</span>}
          {running && job.paused && (
            <span className="chip chip-gold q-tag">
              <Icon name="pause" size={11} />
              {t(`gov.paused.${job.paused}`)}
            </span>
          )}
        </div>
        {sub && (
          <div className="q-sub" dir="auto">
            {sub}
          </div>
        )}
        {running && (
          <div className="q-progress">
            <ProgressBar value={job.progress} />
            <span className="muted">{jobLabel(job, t, num)}</span>
          </div>
        )}
      </div>
      <div className="q-eta">
        {running ? (
          job.paused ? (
            <span className="muted">
              {t("queue.paused_eta")}
              {job.eta_seconds != null && ` · ${t("queue.left", { time: fmtEta(job.eta_seconds, num, t) })}`}
            </span>
          ) : (
            job.eta_seconds != null && <span>{t("queue.left", { time: fmtEta(job.eta_seconds, num, t) })}</span>
          )
        ) : job.eta_finish_seconds != null ? (
          <span className="muted">{t("queue.done_in", { time: fmtEta(job.eta_finish_seconds, num, t) })}</span>
        ) : (
          <span className="muted">{job.lane === "gpu" ? t("job.waiting") : t("status.queued")}</span>
        )}
      </div>
      <div className="q-actions">
        {!running && (
          <>
            <button
              className="btn btn-sm btn-ghost icon-btn"
              disabled={pos <= 1}
              onClick={() => onMove(pos - 2)}
              aria-label={t("queue.up")}
              title={t("queue.up")}
            >
              <Icon name="chevron-up" />
            </button>
            <button
              className="btn btn-sm btn-ghost icon-btn"
              disabled={pos >= queuedCount}
              onClick={() => onMove(pos)}
              aria-label={t("queue.down")}
              title={t("queue.down")}
            >
              <Icon name="chevron-down" />
            </button>
          </>
        )}
        <button className="btn btn-sm btn-ghost" onClick={cancel}>
          {t("job.cancel")}
        </button>
      </div>
    </li>
  );
}

function HistoryRow({ job, projects }: { job: Job; projects: Map<string, string> }) {
  const { t, num, relTime } = useI18n();
  const toast = useToast();
  const { title, sub } = jobTitle(job, t, projects);
  const link = openLink(job);
  const when = job.finished ? relTime(new Date(job.finished * 1000).toISOString()) : "";
  const took = job.started && job.finished ? Math.max(0, job.finished - job.started) : null;
  const retry = () =>
    api
      .retryJob(job.id)
      .then(() => toast({ kind: "ok", text: t("queue.retried") }))
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  return (
    <li className="q-row q-done">
      <span className={`q-state q-${job.status}`} aria-hidden="true">
        <Icon name={job.status === "done" ? "check" : job.status === "error" ? "alert" : "x"} size={14} />
      </span>
      <span className="q-icon" aria-hidden="true">
        <Icon name={KIND_ICON[job.kind] ?? "clock"} size={15} />
      </span>
      <div className="q-main">
        <div className="q-title" dir="auto">
          {link ? <a href={link}>{title}</a> : title}
        </div>
        <div className="q-sub" dir="auto">
          <span className={`status-word s-${job.status}`}>{t(`queue.status.${job.status}`)}</span>
          {sub && <> · {sub}</>}
        </div>
        {job.status === "error" && job.error && (
          <div className="q-error">
            {job.error.message}
            {job.error.hint && <div className="muted">{job.error.hint}</div>}
          </div>
        )}
      </div>
      <div className="q-eta muted">
        {when}
        {took != null && job.status === "done" && <div className="mono">{fmtEta(took, num, t)}</div>}
      </div>
      <div className="q-actions">
        {(job.status === "error" || job.status === "cancelled") && (
          <button className="btn btn-sm" onClick={retry}>
            <Icon name="refresh" />
            {t("common.retry")}
          </button>
        )}
        <button
          className="btn btn-sm btn-ghost icon-btn"
          onClick={() => api.forgetJob(job.id)}
          aria-label={t("queue.remove")}
          title={t("queue.remove")}
        >
          <Icon name="x" />
        </button>
      </div>
    </li>
  );
}

// ------------------------------------------------------------------ batch render

function BatchRender({ onQueued }: { onQueued: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { finishedTick } = useJobs();
  const [items, setItems] = useState<AcceptedOverview[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [rerender, setRerender] = useState(false);
  const [busy, setBusy] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    api.queueAccepted().then((list) => {
      setItems(list);
      if (first.current) {
        first.current = false;
        const todo = list.filter((p) => p.to_render > 0);
        setPicked(new Set((todo.length ? todo : list).map((p) => p.project_id)));
      }
    });
  }, [finishedTick]);

  const count = (items ?? [])
    .filter((p) => picked.has(p.project_id))
    .reduce((a, p) => a + (rerender ? p.accepted : p.to_render), 0);

  const queue = async () => {
    setBusy(true);
    try {
      const r = await api.queueRender([...picked], rerender);
      toast({ kind: "ok", text: t("queue.queued", { n: r.queued }) });
      onQueued();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };

  return (
    <section className="card q-card">
      <div className="q-card-head">
        <div>
          <h2 className="section-title">{t("queue.batch_title")}</h2>
          <p className="muted q-card-desc">{t("queue.batch_desc")}</p>
        </div>
      </div>
      {items == null ? (
        <div className="skeleton" style={{ height: 60 }} />
      ) : items.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          {t("queue.batch_empty")}
        </p>
      ) : (
        <>
          <ul className="batch-list">
            {items.map((p) => {
              const on = picked.has(p.project_id);
              return (
                <li key={p.project_id}>
                  <label className="batch-item">
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={(e) => {
                        const next = new Set(picked);
                        if (e.target.checked) next.add(p.project_id);
                        else next.delete(p.project_id);
                        setPicked(next);
                      }}
                    />
                    <span className="batch-title" dir="auto">
                      {p.title}
                    </span>
                    <span className="muted batch-meta">
                      {t("queue.batch_counts", { n: p.accepted, todo: p.to_render })}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <div className="batch-foot">
            <label className="toggle-line">
              <Toggle checked={rerender} onChange={setRerender} label={t("queue.rerender")} />
              <span>{t("queue.rerender")}</span>
            </label>
            <span style={{ flex: 1 }} />
            <button className="btn btn-primary" disabled={!count || busy} onClick={queue}>
              <Icon name="film" />
              {count ? t("queue.render_n", { n: count }) : t("queue.nothing")}
            </button>
          </div>
          {!rerender && count === 0 && picked.size > 0 && (
            <p className="muted" style={{ margin: "8px 0 0", fontSize: 12.5 }}>
              {t("queue.all_current")}
            </p>
          )}
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ shutdown

function ShutdownCard() {
  const { t } = useI18n();
  const toast = useToast();
  const { shutdown } = useJobs();
  const [state, setState] = useState(shutdown);
  useEffect(() => setState(shutdown), [shutdown]);
  if (!state) return null;
  const set = (v: boolean) =>
    api
      .setShutdown(v)
      .then(setState)
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  return (
    <section className="card q-card">
      <div className="toggle-line" style={{ alignItems: "flex-start" }}>
        <Toggle checked={state.enabled} onChange={set} label={t("queue.shutdown")} />
        <div>
          <div style={{ fontWeight: 550 }}>{t("queue.shutdown")}</div>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {state.supported ? t("queue.shutdown_desc", { s: state.seconds }) : t("queue.shutdown_unsupported")}
            {state.dry_run && <> · {t("queue.shutdown_dry")}</>}
          </div>
          {state.error && <div className="q-error">{state.error}</div>}
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ page

export default function Queue() {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs } = useJobs();
  const [view, setView] = useState<QueueView | null>(null);
  const [projects, setProjects] = useState<Map<string, string>>(new Map());
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const timer = useRef<number>();
  const lastFetch = useRef(0);

  const refresh = () => api.queue().then(setView).catch(() => {});

  // Follow the live job list, at most about once a second.
  useEffect(() => {
    const wait = Math.max(0, 900 - (Date.now() - lastFetch.current));
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      lastFetch.current = Date.now();
      refresh();
    }, wait);
    return () => window.clearTimeout(timer.current);
  }, [jobs]);

  useEffect(() => {
    api.projects().then((ps: ProjectSummary[]) => setProjects(new Map(ps.map((p) => [p.id, p.title]))));
  }, []);

  const gpu = view?.lanes.gpu ?? [];
  const io = view?.lanes.io ?? [];
  const net = view?.lanes.net ?? [];
  const queuedGpu = gpu.filter((j) => j.status === "queued");
  const history = view?.history ?? [];
  const activeCount = jobs.filter(isActive).length;

  const move = async (job: Job, to: number) => {
    try {
      await api.moveJob(job.id, to);
      refresh();
    } catch (e: any) {
      toast({ kind: "err", text: e.message });
    }
  };

  const dragFor = (job: Job, list: Job[]) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      setDrag(job.id);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", job.id);
    },
    onDragEnd: () => {
      setDrag(null);
      setOver(null);
    },
    onDragOver: (e: React.DragEvent) => {
      if (!drag || drag === job.id) return;
      e.preventDefault();
      setOver(job.id);
    },
    onDragLeave: () => setOver((o) => (o === job.id ? null : o)),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      const moving = list.find((j) => j.id === drag);
      setDrag(null);
      setOver(null);
      if (!moving) return;
      move(moving, list.indexOf(job));
    },
  });

  const grouped = useMemo(() => {
    let pos = 0;
    return gpu.map((j) => ({ job: j, pos: j.status === "queued" ? ++pos : 0 }));
  }, [gpu]);

  return (
    <main className="page page-narrow queue-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("queue.title")}</h1>
          <p className="lede">{t("queue.lede")}</p>
        </div>
        {gpu.length > 0 && (
          <div className="q-total">
            <span className="muted">{t("queue.total")}</span>
            <b className="mono">{view?.eta_total_seconds != null ? fmtEta(view.eta_total_seconds, num, t) : "–"}</b>
          </div>
        )}
      </div>

      <div className="q-top">
        <BatchRender onQueued={refresh} />
        <ShutdownCard />
      </div>

      <section className="q-section" aria-labelledby="q-now">
        <div className="q-section-head">
          <h2 className="section-title" id="q-now">
            {t("queue.gpu")} <span className="count mono">{gpu.length}</span>
          </h2>
          {activeCount > 1 && (
            <button className="btn btn-sm btn-ghost" onClick={() => api.queueCancel({}).then(refresh)}>
              {t("queue.cancel_all")}
            </button>
          )}
        </div>
        {gpu.length === 0 ? (
          <div className="q-empty muted">
            <Icon name="check" /> {t("queue.empty")}
          </div>
        ) : (
          <ol className="q-list">
            {grouped.map(({ job, pos }) => (
              <QueueRow
                key={job.id}
                job={job}
                pos={pos}
                queuedCount={queuedGpu.length}
                projects={projects}
                onMove={(to) => move(job, to)}
                dragProps={dragFor(job, queuedGpu)}
                dragOver={over === job.id}
              />
            ))}
          </ol>
        )}
        {queuedGpu.length > 1 && <p className="muted q-hint">{t("queue.drag_hint")}</p>}
      </section>

      {io.length > 0 && (
        <section className="q-section" aria-labelledby="q-io">
          <div className="q-section-head">
            <h2 className="section-title" id="q-io">
              {t("queue.io")} <span className="count mono">{io.length}</span>
            </h2>
          </div>
          <ol className="q-list">
            {io.map((job, i) => (
              <QueueRow
                key={job.id}
                job={job}
                pos={i + 1}
                queuedCount={0}
                projects={projects}
                onMove={() => {}}
                dragProps={{}}
                dragOver={false}
              />
            ))}
          </ol>
        </section>
      )}

      {net.length > 0 && (
        <section className="q-section" aria-labelledby="q-net">
          <div className="q-section-head">
            <h2 className="section-title" id="q-net">
              {t("queue.net")} <span className="count mono">{net.length}</span>
            </h2>
          </div>
          <ol className="q-list">
            {net.map((job, i) => (
              <QueueRow
                key={job.id}
                job={job}
                pos={i + 1}
                queuedCount={0}
                projects={projects}
                onMove={() => {}}
                dragProps={{}}
                dragOver={false}
              />
            ))}
          </ol>
        </section>
      )}

      {history.length > 0 && (
        <section className="q-section" aria-labelledby="q-hist">
          <div className="q-section-head">
            <h2 className="section-title" id="q-hist">
              {t("queue.history")}
            </h2>
            <button className="btn btn-sm btn-ghost" onClick={() => api.queueClear().then(refresh)}>
              {t("queue.clear")}
            </button>
          </div>
          <ol className="q-list">
            {history.map((job) => (
              <HistoryRow key={job.id} job={job} projects={projects} />
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
