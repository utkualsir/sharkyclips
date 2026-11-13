import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionPill } from "../components/EasyAuto";
import { ApiError, easyApi, uploadEasyFile, urls, type EasyProjectRow, type Mode } from "../api";
import { EasyProgress, ModeChip } from "../components/Easy";
import { Icon } from "../components/Icons";
import { DeleteDialog, useUndoToast } from "../components/Trash";
import { ProgressBar } from "../components/ui";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { useMeta } from "../meta";
import { go, href } from "../router";

const PENDING = "sc-easy-pending"; // the import job this browser is waiting for (survives a reload)

function readPending(): string | null {
  try {
    return sessionStorage.getItem(PENDING);
  } catch {
    return null;
  }
}
function writePending(id: string | null) {
  try {
    if (id) sessionStorage.setItem(PENDING, id);
    else sessionStorage.removeItem(PENDING);
  } catch {
    /* ignore */
  }
}

/** Easy mode home: one big drop zone, one button. */
export default function EasyHome() {
  const { t, num } = useI18n();
  const meta = useMeta();
  const { jobs, finishedTick } = useJobs();
  const [link, setLink] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<Mode | "auto">("auto");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [upload, setUpload] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pending, setPending] = useState<string | null>(readPending);
  const [recent, setRecent] = useState<EasyProjectRow[] | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const undoDelete = useUndoToast();
  const input = useRef<HTMLInputElement>(null);
  const abortRef = useRef<() => void>();

  const load = useCallback(() => {
    easyApi.projects().then(setRecent).catch(() => setRecent([]));
  }, []);
  useEffect(load, [load, finishedTick]);

  // Dropping a video anywhere on this screen works too.
  useEffect(() => {
    const over = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) {
        e.preventDefault();
        setDrag(true);
      }
    };
    const drop = (e: DragEvent) => {
      if (!e.dataTransfer?.files?.length) return;
      e.preventDefault();
      setDrag(false);
      pick(e.dataTransfer.files[0]);
    };
    const leave = (e: DragEvent) => !e.relatedTarget && setDrag(false);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    window.addEventListener("dragleave", leave);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
      window.removeEventListener("dragleave", leave);
    };
  }, []);

  const job = pending ? jobs.find((j) => j.id === pending) : undefined;
  // The import finished: its project opens by itself.
  useEffect(() => {
    if (!job) return;
    if (job.status === "done" && job.project_id) {
      writePending(null);
      go(href.project(job.project_id));
    } else if (job.status === "error" || job.status === "cancelled") {
      writePending(null);
      setPending(null);
      if (job.error) setError(new ApiError(job.error.message, job.error.hint, 400));
    }
  }, [job]);
  // A reload after the job left the list: forget it.
  useEffect(() => {
    if (pending && jobs.length && !job) {
      writePending(null);
      setPending(null);
    }
  }, [pending, jobs, job]);

  const pick = (f: File | null | undefined) => {
    if (!f) return;
    setFile(f);
    setLink("");
    setError(null);
  };

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      let j;
      if (file) {
        const up = uploadEasyFile(file, mode, setUpload);
        abortRef.current = up.abort;
        j = await up.promise;
      } else {
        const v = link.trim();
        j = await easyApi.create(/^https?:\/\//i.test(v) ? { url: v, mode, language: "auto" } : { path: v, mode, language: "auto" });
      }
      writePending(j.id);
      setPending(j.id);
      setFile(null);
      setLink("");
    } catch (e) {
      if (e instanceof ApiError && e.message === "aborted") return;
      setError(e instanceof ApiError ? e : new ApiError(String(e), null, 0));
    } finally {
      setBusy(false);
      setUpload(null);
    }
  };

  const can = !busy && !pending && (!!file || link.trim().length > 3);
  const working = !!pending;

  return (
    <main className="page ez-page">
      <div className="ez-hero">
        <ConnectionPill />
        <h1 className="display">{t("easy.create_title")}</h1>
        <p className="lede">{t("easy.create_lede")}</p>
      </div>

      {working ? (
        <div className="ez-working">
          <EasyProgress
            steps={[
              { key: "download", status: "active", progress: job?.status === "running" ? job.progress : null },
              { key: "transcribe", status: "todo", progress: null },
              { key: "find", status: "todo", progress: null },
              { key: "titles", status: "todo", progress: null },
              { key: "render", status: "todo", progress: null },
            ]}
            eta={null}
          />
        </div>
      ) : (
        <form
          className="ez-create"
          onSubmit={(e) => {
            e.preventDefault();
            if (can) start();
          }}
        >
          <div
            className={`ez-drop${drag ? " drag" : ""}${file ? " has-file" : ""}`}
            data-tour="drop"
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setDrag(false);
              pick(e.dataTransfer.files?.[0]);
            }}
          >
            <span className="ez-drop-icon" aria-hidden="true">
              <Icon name={file ? "film" : "upload"} size={30} />
            </span>
            {file ? (
              <div className="ez-file">
                <strong dir="auto">{file.name}</strong>
                <span className="muted mono">{(file.size / 1024 ** 3).toFixed(2)} GB</span>
                <button type="button" className="link-btn" onClick={() => setFile(null)}>
                  {t("easy.change_video")}
                </button>
              </div>
            ) : (
              <>
                <strong className="ez-drop-title">{t("easy.drop_title")}</strong>
                <label className="ez-link">
                  <span className="sr-only">{meta?.is_local ? t("easy.link_label_local") : t("easy.link_label")}</span>
                  <Icon name="link" size={18} />
                  <input
                    className="input"
                    dir="ltr"
                    value={link}
                    placeholder={t("easy.link_placeholder")}
                    onChange={(e) => setLink(e.target.value)}
                    onPaste={(e) => {
                      const f = e.clipboardData.files?.[0];
                      if (f) {
                        e.preventDefault();
                        pick(f);
                      }
                    }}
                  />
                </label>
                <button type="button" className="link-btn ez-choose" onClick={() => input.current?.click()}>
                  {t("easy.choose_file")}
                </button>
              </>
            )}
            <input ref={input} type="file" accept="video/*,.mkv,.flv,.ts" hidden onChange={(e) => pick(e.target.files?.[0])} />
            {upload != null && (
              <div className="ez-upload-bar">
                <ProgressBar value={upload} label={t("easy.sending")} />
                <span className="muted">{t("easy.sending_pct", { p: num(Math.round(upload * 100)) })}</span>
              </div>
            )}
          </div>

          <div className="ez-create-row">
            <ModeChip value={mode} onChange={setMode} allowAuto />
            <button type="submit" className="btn btn-primary btn-xl" disabled={!can} data-tour="find">
              {busy ? <span className="spinner" style={{ borderTopColor: "currentColor" }} /> : <Icon name="sparkles" />}
              {t("easy.find_clips")}
            </button>
          </div>
          {error && (
            <div className="notice notice-danger" role="alert">
              <Icon name="alert" />
              <div>
                <div className="notice-title">{error.message}</div>
                {error.hint && <div className="muted">{error.hint}</div>}
              </div>
            </div>
          )}
        </form>
      )}

      {recent && recent.length > 0 && (
        <section className="ez-recent" aria-labelledby="ez-recent-title">
          <h2 id="ez-recent-title">{t("easy.recent")}</h2>
          <ul className="ez-recent-list">
            {recent.slice(0, 8).map((p) => (
              <li key={p.id}>
                <a className="ez-recent-item" href={href.project(p.id)}>
                  <span className="ez-recent-thumb">
                    {p.duration ? <img src={urls.thumb(p.id, String(p.clips))} alt="" loading="lazy" /> : <Icon name="film" />}
                  </span>
                  <span className="ez-recent-text">
                    <b dir="auto">{p.title}</b>
                    <span className="muted">
                      {p.busy ? t("easy.recent_working") : p.clips ? t("easy.recent_clips", { n: p.clips }) : t("easy.recent_empty")}
                      {p.duration ? ` · ${fmtTime(p.duration)}` : ""}
                    </span>
                  </span>
                  <Icon name="chevron-right" size={18} className="flip-rtl" />
                </a>
                <button className="btn btn-ghost icon-btn ez-recent-del" onClick={() => setDeleting(p.id)}
                  aria-label={t("trash.delete_named", { title: p.title })} title={t("trash.delete_project")}>
                  <Icon name="trash" size={15} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {deleting && (
        <DeleteDialog
          projectId={deleting}
          clipIds={null}
          onClose={() => setDeleting(null)}
          onDeleted={(item) => {
            setDeleting(null);
            load();
            undoDelete(item, load);
          }}
        />
      )}
      <p className="ez-trash-link">
        <a className="link-btn" href={href.trash}>
          <Icon name="trash" size={13} /> {t("trash.title")}
        </a>
      </p>
    </main>
  );
}
