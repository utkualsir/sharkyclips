import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, uploadFile, urls, type Job, type Mode, type ProjectSummary } from "../api";
import { Icon } from "../components/Icons";
import { DeleteDialog, useUndoToast } from "../components/Trash";
import { fmtBytes as fmtSize } from "../format";
import { trashApi } from "../trash";
import { jobLabel, Modal, ProgressBar } from "../components/ui";
import { fmtTime, sourceLabel } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useMeta } from "../meta";
import { href } from "../router";
import { useToast } from "../toast";

const MODE_ICON: Record<string, string> = { gaming: "gamepad", study: "book", music: "music" };

function ProjectCard({ p, job, size, onDelete }: { p: ProjectSummary; job: Job | undefined; size?: number; onDelete: () => void }) {
  const { t, num } = useI18n();
  const [imgOk, setImgOk] = useState(true);
  let status: JSX.Element;
  if (job) {
    status = (
      <span className="status status-running">
        <span className="dot" />
        {jobLabel(job, t, num)}
      </span>
    );
  } else if (p.state === "error") {
    status = (
      <span className="status status-error" title={p.last_error?.message}>
        <span className="dot" />
        {t("job.failed", { kind: t(`kind.${p.last_error_kind}`) })}
      </span>
    );
  } else if (p.state === "ready") {
    status = (
      <span className="status status-ready">
        <span className="dot" />
        {t("library.candidates_ready", { n: p.candidates ?? 0 })}
      </span>
    );
  } else {
    status = (
      <span className="status">
        <span className="dot" />
        {t(`status.${p.state}`)}
      </span>
    );
  }
  const src = p.source.type === "file" ? t("library.source_file") : sourceLabel(p.source.value);
  return (
    <div className="pcard-wrap">
    <a className="card pcard" href={href.project(p.id)}>
      <div className="pcard-thumb">
        {imgOk && p.duration ? (
          <img src={urls.thumb(p.id, p.candidates ? String(p.candidates) : null)} alt="" loading="lazy" onError={() => setImgOk(false)} />
        ) : (
          <div className="placeholder">
            <Icon name="film" size={28} />
          </div>
        )}
        {p.mode && (
          <span className="pcard-mode">
            <span className="chip">
              <Icon name={MODE_ICON[p.mode]} size={12} />
              {t(`mode.${p.mode}`)}
            </span>
          </span>
        )}
        {p.duration != null && <span className="pcard-duration tc">{fmtTime(p.duration)}</span>}
      </div>
      <div className="pcard-body">
        <h2 className="pcard-title" dir="auto">
          {p.title}
        </h2>
        <div className="pcard-source">
          <Icon name={p.source.type === "file" ? "file" : "link"} size={13} />
          <span dir="auto">{[src, p.source.uploader].filter(Boolean).join(" · ")}</span>
        </div>
        <div className="pcard-foot">
          {status}
          {p.clips > 0 && <span className="chip chip-gold">{t("library.clips", { n: p.clips })}</span>}
          {size != null && size > 0 && <span className="pcard-size mono">{fmtSize(size)}</span>}
        </div>
        {job && <ProgressBar value={job.status === "queued" ? null : job.progress} />}
      </div>
    </a>
      <button className="btn btn-ghost icon-btn pcard-del" onClick={onDelete} aria-label={t("trash.delete_named", { title: p.title })} title={t("trash.delete_project")}>
        <Icon name="trash" size={15} />
      </button>
    </div>
  );
}

function PendingImportCard({ job }: { job: Job }) {
  const { t, num } = useI18n();
  return (
    <div className="card pcard" style={{ cursor: "default" }}>
      <div className="pcard-thumb">
        <div className="placeholder skeleton" style={{ borderRadius: 0 }} />
      </div>
      <div className="pcard-body">
        <h2 className="pcard-title" dir="auto">
          {job.params.title}
        </h2>
        <div className="pcard-foot">
          <span className="status status-running">
            <span className="dot" />
            {jobLabel(job, t, num)}
          </span>
        </div>
        <ProgressBar value={job.status === "queued" ? null : job.progress} />
      </div>
    </div>
  );
}

export function NewProjectModal({ onClose }: { onClose: () => void }) {
  const { t, num } = useI18n();
  const meta = useMeta();
  const toast = useToast();
  const [tab, setTab] = useState<"link" | "file">("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<Mode>("gaming");
  const [language, setLanguage] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [upload, setUpload] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [drag, setDrag] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const abortRef = useRef<() => void>();

  useEffect(() => {
    api.settings().then((s) => setMode(s.default_mode)).catch(() => {});
  }, []);

  const pickFile = (f: File | undefined | null) => {
    if (f) {
      setFile(f);
      setTab("file");
      setError(null);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (tab === "link") {
        const v = url.trim();
        const isUrl = /^https?:\/\//i.test(v);
        await api.create(isUrl ? { url: v, mode, language } : { path: v, mode, language });
      } else if (file) {
        const up = uploadFile(file, mode, language, setUpload);
        abortRef.current = up.abort;
        await up.promise;
      }
      toast({ kind: "ok", text: t("new.pipeline_note") });
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.message === "aborted") return;
      setError(e instanceof ApiError ? e : new ApiError(String(e), null, 0));
    } finally {
      setBusy(false);
      setUpload(null);
    }
  };

  const canSubmit = !busy && (tab === "link" ? url.trim().length > 3 : !!file);
  const modes: Mode[] = ["gaming", "study", "music"];

  return (
    <Modal
      title={t("new.title")}
      onClose={() => {
        abortRef.current?.();
        onClose();
      }}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={submit}>
            {busy && <span className="spinner" style={{ borderTopColor: "currentColor" }} />}
            {upload != null ? t("new.uploading", { p: num(Math.round(upload * 100)) }) : t("new.submit")}
          </button>
        </>
      }
    >
      <div className="segmented block" role="tablist">
        <button type="button" role="tab" aria-pressed={tab === "link"} onClick={() => setTab("link")}>
          <Icon name="link" /> &nbsp;{t("new.tab_link")}
        </button>
        <button type="button" role="tab" aria-pressed={tab === "file"} onClick={() => setTab("file")}>
          <Icon name="upload" /> &nbsp;{t("new.tab_file")}
        </button>
      </div>

      {tab === "link" ? (
        <label className="field">
          <span className="field-label">{meta?.is_local ? t("new.url_label_local") : t("new.url_label")}</span>
          <input
            className="input"
            dir="ltr"
            value={url}
            placeholder={t("new.url_placeholder")}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()}
            onPaste={(e) => {
              const f = e.clipboardData.files?.[0];
              if (f) pickFile(f);
            }}
          />
          <span className="field-hint">{t("new.url_hint")}</span>
        </label>
      ) : (
        <div
          className={`dropzone${drag ? " drag" : ""}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            pickFile(e.dataTransfer.files?.[0]);
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileInput.current?.click()}
        >
          <Icon name={file ? "film" : "upload"} size={26} />
          {file ? (
            <>
              <strong dir="auto">{file.name}</strong>
              <span className="mono">{(file.size / 1024 ** 3).toFixed(2)} GB</span>
            </>
          ) : (
            <>
              <strong>{t("new.drop_title")}</strong>
              <span>{t("new.drop_or")}</span>
              <span style={{ fontSize: 12 }}>{t("new.drop_types")}</span>
            </>
          )}
          {upload != null && (
            <div style={{ width: "100%", maxWidth: 320 }}>
              <ProgressBar value={upload} />
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept="video/*,.mkv,.flv,.ts"
            hidden
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
        </div>
      )}

      <div className="field">
        <span className="field-label">{t("new.mode")}</span>
        <div className="mode-grid">
          {modes.map((m) => (
            <button key={m} type="button" className="mode-opt" aria-pressed={mode === m} onClick={() => setMode(m)}>
              <b>
                <Icon name={MODE_ICON[m]} size={14} /> {t(`mode.${m}`)}
              </b>
              <span>{t(`mode.${m}_desc`)}</span>
            </button>
          ))}
        </div>
      </div>

      <label className="field">
        <span className="field-label">{t("new.language")}</span>
        <select className="select" value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="auto">{t("new.lang_auto")}</option>
          {UI_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
      </label>

      {error && (
        <div className="notice notice-danger">
          <Icon name="alert" />
          <div>
            <div className="notice-title">{error.message}</div>
            {error.hint && <div className="muted">{error.hint}</div>}
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function Library() {
  const { t } = useI18n();
  const { jobs, finishedTick } = useJobs();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [sizes, setSizes] = useState<Record<string, number>>({});
  const [trashCount, setTrashCount] = useState(0);
  const undo = useUndoToast();

  const load = useCallback(() => {
    api.projects()
      .then((p) => {
        setProjects(p);
        setFailed(false);
      })
      .catch(() => setFailed(true));
    trashApi
      .disk()
      .then((d) => {
        setSizes(Object.fromEntries(d.projects.map((u) => [u.project_id, u.total])));
        setTrashCount(d.trash_count);
      })
      .catch(() => {});
  }, []);

  useEffect(load, [load, finishedTick]);

  // Global drop: dropping a video anywhere on the library opens the dialog.
  useEffect(() => {
    const over = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) {
        e.preventDefault();
        setShowNew(true);
      }
    };
    window.addEventListener("dragover", over);
    return () => window.removeEventListener("dragover", over);
  }, []);

  const activeByProject = new Map<string, Job>();
  for (const j of jobs.filter(isActive)) {
    if (!j.project_id) continue;
    const cur = activeByProject.get(j.project_id);
    if (!cur || (j.status === "running" && cur.status !== "running")) activeByProject.set(j.project_id, j);
  }
  const pendingImports = jobs.filter((j) => j.kind === "import" && isActive(j) && !j.project_id);
  const known = new Set(projects?.map((p) => p.id));
  // A project whose import just finished but the list hasn't reloaded yet
  const stale = jobs.some((j) => j.project_id && isActive(j) && !known.has(j.project_id));
  useEffect(() => {
    if (stale) load();
  }, [stale, load]);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("library.title")}</h1>
          <p className="lede">{t("library.lede")}</p>
        </div>
        <div className="inline-row" style={{ flexWrap: "wrap" }}>
          <a className="btn btn-ghost" href={href.trash}>
            <Icon name="trash" size={15} /> {t("trash.title")}
            {trashCount > 0 && <span className="nav-count mono">{trashCount}</span>}
          </a>
          <button className="btn btn-primary btn-lg" onClick={() => setShowNew(true)}>
            <Icon name="plus" />
            {t("library.new")}
          </button>
        </div>
      </div>

      {failed && (
        <div className="notice notice-danger" style={{ marginBottom: 16 }}>
          <Icon name="alert" />
          <div>{t("common.offline")}</div>
        </div>
      )}

      {projects === null && !failed ? (
        <div className="grid-cards">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card" style={{ height: 290, overflow: "hidden" }}>
              <div className="skeleton" style={{ height: "56%", borderRadius: 0 }} />
              <div style={{ padding: 16, display: "grid", gap: 10 }}>
                <div className="skeleton" style={{ height: 14, width: "80%" }} />
                <div className="skeleton" style={{ height: 12, width: "50%" }} />
              </div>
            </div>
          ))}
        </div>
      ) : projects && projects.length === 0 && pendingImports.length === 0 ? (
        <div className="empty">
          <Icon name="film" size={30} />
          <h2 className="display">{t("library.empty_title")}</h2>
          <p style={{ maxWidth: "46ch", margin: 0 }}>{t("library.empty_body")}</p>
          <button className="btn btn-primary" onClick={() => setShowNew(true)} style={{ marginTop: 8 }}>
            <Icon name="plus" />
            {t("library.new")}
          </button>
        </div>
      ) : (
        <div className="grid-cards">
          {pendingImports.map((j) => (
            <PendingImportCard key={j.id} job={j} />
          ))}
          {projects?.map((p) => (
            <ProjectCard key={p.id} p={p} job={activeByProject.get(p.id)} size={sizes[p.id]} onDelete={() => setDeleting(p.id)} />
          ))}
          <button className="new-card" onClick={() => setShowNew(true)}>
            <span className="plus">
              <Icon name="plus" size={20} />
            </span>
            {t("library.new")}
          </button>
        </div>
      )}
      {showNew && <NewProjectModal onClose={() => setShowNew(false)} />}
      {deleting && (
        <DeleteDialog
          projectId={deleting}
          clipIds={null}
          onClose={() => setDeleting(null)}
          onDeleted={(item) => {
            setDeleting(null);
            load();
            undo(item, load);
          }}
        />
      )}
    </main>
  );
}

