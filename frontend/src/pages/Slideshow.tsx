// 1.2.72 Photo slideshow: drop 2-20 photos (before -> progress -> result), order them, pick the look,
// preview, export a 9:16 video and share it with the normal Share flow.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import { Icon } from "../components/Icons";
import { DeleteDialog, useUndoToast } from "../components/Trash";
import { ProgressBar, Segmented, Toggle } from "../components/ui";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { useMeta } from "../meta";
import { go, href } from "../router";
import {
  handFiles,
  isPhoto,
  PHOTO_ACCEPT,
  slideshowApi,
  slideUrls,
  takeFiles,
  uploadPhoto,
  type SlideshowRow,
  type SlideshowView,
  type Transition,
} from "../slideshow";
import { useToast } from "../toast";
import "../slideshow.css";

function secs(n: number, num: (n: number, digits?: number) => string): string {
  const r = Math.round(n * 10) / 10;
  return num(r, Number.isInteger(r) ? 0 : 1); // 31.5 s stays 31.5 (num() alone rounds to whole numbers)
}

/** #/slideshow: start a new one (drop photos) + the slideshows made before. */
export function SlideshowList() {
  const { t, num } = useI18n();
  const toast = useToast();
  const [rows, setRows] = useState<SlideshowRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const undoDelete = useUndoToast();
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => {
    slideshowApi.list().then(setRows).catch(() => setRows([]));
  }, []);
  useEffect(load, [load]);

  const start = async (files: File[]) => {
    if (busy) return;
    setBusy(true);
    try {
      const v = await slideshowApi.create();
      handFiles(v.id, files.filter(isPhoto));
      go(href.slideshow(v.id));
    } catch (e) {
      const err = e as ApiError;
      toast({ kind: "err", text: err.message, hint: err.hint });
      setBusy(false);
    }
  };

  return (
    <main className="page ss-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("slideshow.title")}</h1>
          <p className="lede">{t("slideshow.lede")}</p>
        </div>
      </div>
      <div
        className={`ss-drop ss-drop-big${drag ? " drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const files = Array.from(e.dataTransfer.files || []);
          if (files.length) start(files);
        }}
      >
        <span className="ss-drop-icon" aria-hidden="true">
          <Icon name="image" size={30} />
        </span>
        <strong>{t("slideshow.drop_title")}</strong>
        <span className="muted">{t("slideshow.drop_hint")}</span>
        <div className="inline-row ss-drop-actions">
          <button type="button" className="btn btn-primary btn-lg" onClick={() => input.current?.click()} disabled={busy}>
            {busy ? <span className="spinner" style={{ borderTopColor: "currentColor" }} /> : <Icon name="plus" />}
            {t("slideshow.choose")}
          </button>
        </div>
        <input
          ref={input}
          type="file"
          multiple
          accept={PHOTO_ACCEPT}
          hidden
          onChange={(e) => {
            const files = Array.from(e.target.files || []);
            e.target.value = "";
            if (files.length) start(files);
          }}
        />
      </div>

      {rows && rows.length > 0 && (
        <section className="ss-recent" aria-labelledby="ss-recent-title">
          <h2 id="ss-recent-title">{t("slideshow.recent")}</h2>
          <ul className="ss-recent-list">
            {rows.map((r) => (
              <li key={r.id}>
                <a className="ss-recent-item" href={href.slideshow(r.id)}>
                  <span className="ss-recent-thumb">
                    {r.first ? <img src={slideUrls.thumb(r.id, r.first)} alt="" loading="lazy" /> : <Icon name="image" />}
                  </span>
                  <span className="ss-recent-text">
                    <b dir="auto">{r.title}</b>
                    <span className="muted">
                      {t("slideshow.row_photos", { n: r.photos })}
                      {r.duration ? `, ${t("slideshow.seconds_short", { s: secs(r.duration, num) })}` : ""}
                    </span>
                  </span>
                  {r.share?.kind === "shared" ? (
                    <span className="chip chip-success">{t("slideshow.row_shared")}</span>
                  ) : r.exported ? (
                    <span className="chip">{t("slideshow.row_ready")}</span>
                  ) : null}
                  <Icon name="chevron-right" size={18} className="flip-rtl" />
                </a>
                <button className="btn btn-ghost icon-btn ss-recent-del" onClick={() => setDeleting(r.id)}
                  aria-label={t("trash.delete_named", { title: r.title })} title={t("trash.delete_project")}>
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
    </main>
  );
}

/** #/slideshow/<id>: the editor. */
export function SlideshowEditor({ id }: { id: string }) {
  const { t, num, lang } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const { jobs, finishedTick } = useJobs();
  const [v, setV] = useState<SlideshowView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [uploading, setUploading] = useState<{ done: number; total: number } | null>(null);
  const [failed, setFailed] = useState<{ name: string; message: string }[]>([]);
  const [drag, setDrag] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [saving, setSaving] = useState<"save" | "open" | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const textTimer = useRef<number | undefined>(undefined);
  const pendingTexts = useRef<Record<string, string>>({});

  const apply = useCallback((nv: SlideshowView) => {
    setV(nv);
    setTexts(Object.fromEntries(nv.photos.map((p) => [p.id, p.text])));
  }, []);

  const load = useCallback(() => {
    slideshowApi
      .get(id)
      .then((nv) => {
        apply(nv);
        setTitle(nv.title);
        setSubject(nv.settings.subject || "");
      })
      .catch((e) => setError(e as ApiError));
  }, [id, apply]);
  useEffect(load, [load]);
  // a preview / export finished: fresh state from the server
  useEffect(() => {
    if (finishedTick) slideshowApi.get(id).then(apply).catch(() => {});
  }, [finishedTick, id, apply]);

  const addFiles = useCallback(
    async (files: File[]) => {
      const photos = files.filter(isPhoto);
      const bad = files.filter((f) => !isPhoto(f)).map((f) => ({ name: f.name, message: t("slideshow.not_photo") }));
      setFailed(bad);
      if (!photos.length) return;
      setUploading({ done: 0, total: photos.length });
      let last: SlideshowView | null = null;
      const errs: { name: string; message: string }[] = [...bad];
      for (let i = 0; i < photos.length; i++) {
        try {
          last = await uploadPhoto(id, photos[i]);
        } catch (e) {
          errs.push({ name: photos[i].name, message: (e as ApiError).message });
          if ((e as ApiError).status === 400 && /20/.test((e as ApiError).message)) break; // full
        }
        setUploading({ done: i + 1, total: photos.length });
      }
      setUploading(null);
      setFailed(errs);
      if (last) apply(last);
    },
    [id, t, apply],
  );

  // photos dropped on the list screen
  useEffect(() => {
    const files = takeFiles(id);
    if (files.length) addFiles(files);
  }, [id, addFiles]);

  const update = async (body: Parameters<typeof slideshowApi.update>[1]) => {
    try {
      apply(await slideshowApi.update(id, body));
    } catch (e) {
      const err = e as ApiError;
      toast({ kind: "err", text: err.message, hint: err.hint });
    }
  };

  const setText = (pid: string, value: string) => {
    setTexts((x) => ({ ...x, [pid]: value }));
    pendingTexts.current[pid] = value;
    window.clearTimeout(textTimer.current);
    textTimer.current = window.setTimeout(() => {
      const body = pendingTexts.current;
      pendingTexts.current = {};
      update({ texts: body });
    }, 600);
  };

  const move = (pid: string, to: number) => {
    if (!v) return;
    const ids = v.photos.map((p) => p.id).filter((x) => x !== pid);
    ids.splice(Math.max(0, Math.min(ids.length, to)), 0, pid);
    // optimistic: the grid moves at once
    setV({ ...v, photos: ids.map((x) => v.photos.find((p) => p.id === x)!), settings: { ...v.settings, order_mode: "manual" } });
    update({ order: ids });
  };

  const removePhoto = async (pid: string) => {
    try {
      const nv = await slideshowApi.remove(id, pid);
      apply(nv);
      toast({
        kind: "ok",
        text: t("slideshow.removed"),
        ms: 8000,
        action: { label: t("trash.undo"), run: () => slideshowApi.restore(id, pid).then(apply).catch(() => {}) },
      });
    } catch (e) {
      toast({ kind: "err", text: (e as ApiError).message });
    }
  };

  const runJob = async (kind: "preview" | "export") => {
    try {
      await (kind === "preview" ? slideshowApi.preview(id) : slideshowApi.export(id));
      slideshowApi.get(id).then(apply).catch(() => {});
    } catch (e) {
      const err = e as ApiError;
      toast({ kind: "err", text: err.message, hint: err.hint });
    }
  };

  const doSave = async (what: "save" | "open") => {
    setSaving(what);
    try {
      if (what === "save") {
        const r = await slideshowApi.save(id);
        setSaved(r.folder);
        toast({ kind: "ok", text: t("slideshow.saved"), hint: r.folder });
      } else {
        const r = await slideshowApi.openFolder(id);
        setSaved(r.folder);
        if (!r.opened) toast({ kind: "info", text: t("slideshow.folder_is"), hint: r.folder });
      }
    } catch (e) {
      const err = e as ApiError;
      toast({ kind: "err", text: err.message, hint: err.hint });
    } finally {
      setSaving(null);
    }
  };

  if (error) {
    return (
      <main className="page ss-page">
        <div className="notice notice-danger" role="alert">
          <Icon name="alert" />
          <div>
            <div className="notice-title">{error.message}</div>
            <a className="link-btn" href={href.slideshows}>{t("slideshow.back")}</a>
          </div>
        </div>
      </main>
    );
  }
  if (!v) {
    return (
      <main className="page ss-page">
        <div className="muted">{t("common.loading")}</div>
      </main>
    );
  }

  const liveJob = (kind: "slideshow_preview" | "slideshow_export") =>
    jobs.find((j) => j.project_id === id && j.kind === kind && (j.status === "queued" || j.status === "running")) ??
    (v.jobs[kind] && (v.jobs[kind]!.status === "queued" || v.jobs[kind]!.status === "running") ? v.jobs[kind] : undefined);
  const lastJob = (kind: "slideshow_preview" | "slideshow_export") =>
    jobs.filter((j) => j.project_id === id && j.kind === kind).sort((a, b) => b.created - a.created)[0] ?? v.jobs[kind];
  const pJob = liveJob("slideshow_preview");
  const eJob = liveJob("slideshow_export");
  const eLast = lastJob("slideshow_export");
  const pLast = lastJob("slideshow_preview");
  const n = v.photos.length;
  const full = n >= v.limits.max_photos;
  const need = Math.max(0, v.limits.min_photos - n);
  const tl = v.timeline;
  const transitionLabel: Record<Transition, string> = {
    crossfade: t("slideshow.tr_crossfade"),
    slide: t("slideshow.tr_slide"),
    zoom: t("slideshow.tr_zoom"),
  };
  const dateFmt = (iso: string | null) => {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleDateString(lang, { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return iso.slice(0, 10);
    }
  };

  return (
    <main
      className="page ss-page"
      onDragOver={(e) => {
        if (e.dataTransfer?.types.includes("Files")) {
          e.preventDefault();
          setDrag(true);
        }
      }}
      onDragLeave={(e) => !e.relatedTarget && setDrag(false)}
      onDrop={(e) => {
        if (!e.dataTransfer?.files?.length) return;
        e.preventDefault();
        setDrag(false);
        addFiles(Array.from(e.dataTransfer.files));
      }}
    >
      <a className="link-btn ss-back" href={href.slideshows}>
        <Icon name="chevron-left" size={14} className="flip-rtl" /> {t("slideshow.back")}
      </a>
      <div className="page-head ss-head">
        <div className="ss-title-wrap">
          <h1 className="display sr-only">{t("slideshow.title")}</h1>
          <label className="field">
            <span className="field-label">{t("slideshow.name")}</span>
            <input
              className="input ss-title"
              dir="auto"
              value={title}
              maxLength={80}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => title.trim() && title !== v.title && update({ title })}
            />
          </label>
        </div>
      </div>

      <div className="ss-layout">
        <div className="ss-main">
          {/* ---------------------------------------------------------- photos */}
          <section className="panel ss-photos" aria-labelledby="ss-photos-h">
            <div className="ss-section-head">
              <h2 id="ss-photos-h">
                {t("slideshow.photos")} <span className="muted mono ss-count">{num(n)} / {num(v.limits.max_photos)}</span>
              </h2>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => update({ sort: "date" })}
                disabled={n < 2}
                aria-pressed={v.settings.order_mode === "date"}
              >
                <Icon name="calendar" size={14} /> {t("slideshow.sort_date")}
              </button>
            </div>
            <p className="field-hint">{n > 1 ? t("slideshow.order_hint") : t("slideshow.drop_hint")}</p>

            {n > 0 && (
              <ol className="ss-grid">
                {v.photos.map((p, i) => (
                  <li
                    key={p.id}
                    className={`ss-card${dragId === p.id ? " dragging" : ""}${overId === p.id && dragId !== p.id ? " over" : ""}`}
                    draggable
                    onDragStart={(e) => {
                      setDragId(p.id);
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData("text/plain", p.id);
                    }}
                    onDragEnd={() => {
                      setDragId(null);
                      setOverId(null);
                    }}
                    onDragOver={(e) => {
                      if (!dragId) return;
                      e.preventDefault();
                      e.stopPropagation();
                      setOverId(p.id);
                    }}
                    onDrop={(e) => {
                      if (!dragId) return;
                      e.preventDefault();
                      e.stopPropagation();
                      move(dragId, i);
                      setDragId(null);
                      setOverId(null);
                    }}
                  >
                    <div className="ss-thumb">
                      <img src={slideUrls.thumb(id, p.id)} alt={t("slideshow.photo_n", { n: i + 1 })} loading="lazy" draggable={false} />
                      <span className="ss-num mono" aria-hidden="true">{num(i + 1)}</span>
                      {p.shown_text && <span className="ss-tag" dir="auto">{p.shown_text}</span>}
                      <span className="ss-grip" aria-hidden="true"><Icon name="grip" size={14} /></span>
                    </div>
                    <div className="ss-card-body">
                      <span className="ss-date muted" title={p.name ?? undefined}>
                        {dateFmt(p.taken_at) ?? t("slideshow.no_date")}
                      </span>
                      <label className="sr-only" htmlFor={`ss-text-${p.id}`}>{t("slideshow.text_label", { n: i + 1 })}</label>
                      <input
                        id={`ss-text-${p.id}`}
                        className="input input-sm"
                        dir="auto"
                        value={texts[p.id] ?? ""}
                        maxLength={v.limits.text_max}
                        placeholder={v.settings.labels ? p.label : t("slideshow.text_placeholder")}
                        onChange={(e) => setText(p.id, e.target.value)}
                      />
                      <div className="ss-card-actions">
                        <button type="button" className="btn btn-ghost icon-btn btn-sm" disabled={i === 0}
                          onClick={() => move(p.id, i - 1)} aria-label={t("slideshow.move_earlier", { n: i + 1 })} title={t("slideshow.move_earlier", { n: i + 1 })}>
                          <Icon name="chevron-left" size={14} className="flip-rtl" />
                        </button>
                        <button type="button" className="btn btn-ghost icon-btn btn-sm" disabled={i === n - 1}
                          onClick={() => move(p.id, i + 1)} aria-label={t("slideshow.move_later", { n: i + 1 })} title={t("slideshow.move_later", { n: i + 1 })}>
                          <Icon name="chevron-right" size={14} className="flip-rtl" />
                        </button>
                        <span style={{ flex: 1 }} />
                        <button type="button" className="btn btn-ghost icon-btn btn-sm" onClick={() => removePhoto(p.id)}
                          aria-label={t("slideshow.remove_n", { n: i + 1 })} title={t("slideshow.remove_n", { n: i + 1 })}>
                          <Icon name="x" size={14} />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            )}

            {!full && (
              <div className={`ss-drop${drag ? " drag" : ""}`}>
                <Icon name="image" size={22} />
                <span>{n ? t("slideshow.add_more") : t("slideshow.drop_title")}</span>
                <button type="button" className="btn btn-sm" onClick={() => input.current?.click()} disabled={!!uploading}>
                  <Icon name="plus" size={14} /> {t("slideshow.choose")}
                </button>
                <input
                  ref={input}
                  type="file"
                  multiple
                  accept={PHOTO_ACCEPT}
                  hidden
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    e.target.value = "";
                    addFiles(files);
                  }}
                />
              </div>
            )}
            {uploading && (
              <div className="ss-uploading">
                <ProgressBar value={uploading.done / uploading.total} label={t("slideshow.adding")} />
                <span className="muted">{t("slideshow.adding_n", { i: num(uploading.done), n: num(uploading.total) })}</span>
              </div>
            )}
            {failed.length > 0 && (
              <div className="notice notice-warn" role="alert">
                <Icon name="alert" />
                <div>
                  <div className="notice-title">{t("slideshow.some_failed")}</div>
                  <ul className="ss-failed">
                    {failed.map((f, i) => (
                      <li key={i}>
                        <b dir="auto">{f.name}</b>: {f.message}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </section>

          {/* ---------------------------------------------------------- look */}
          <section className="panel ss-look" aria-labelledby="ss-look-h">
            <h2 id="ss-look-h">{t("slideshow.look")}</h2>
            <div className="field">
              <label className="field-label" htmlFor="ss-seconds">
                {t("slideshow.per_photo", { s: secs(v.settings.seconds, num) })}
              </label>
              <input
                id="ss-seconds"
                type="range"
                className="ss-range"
                min={v.limits.seconds[0]}
                max={v.limits.seconds[1]}
                step={0.5}
                value={v.settings.seconds}
                onChange={(e) => setV({ ...v, settings: { ...v.settings, seconds: Number(e.target.value) } })}
                onPointerUp={(e) => update({ seconds: Number((e.target as HTMLInputElement).value) })}
                onKeyUp={(e) => update({ seconds: Number((e.target as HTMLInputElement).value) })}
              />
            </div>
            <div className="field">
              <span className="field-label" id="ss-tr-label">{t("slideshow.transition")}</span>
              <Segmented
                value={v.settings.transition}
                label={t("slideshow.transition")}
                options={v.transitions.map((x) => ({ value: x, label: transitionLabel[x] }))}
                onChange={(x) => update({ transition: x })}
              />
            </div>
            <div className="toggle-row ss-toggle">
              <Toggle checked={v.settings.labels} onChange={(x) => update({ labels: x })} label={t("slideshow.labels")} />
              <div>
                <div>{t("slideshow.labels")}</div>
                <div className="field-hint" dir="auto">{v.labels_words.join(" → ")}</div>
              </div>
            </div>
            <div className="toggle-row ss-toggle">
              <Toggle checked={v.settings.outro} onChange={(x) => update({ outro: x })} label={t("slideshow.outro")} />
              <div>
                <div>{t("slideshow.outro")}</div>
                <div className="field-hint">{t("slideshow.outro_hint", { s: secs(v.limits.outro_s, num) })}</div>
              </div>
            </div>
            <label className="field">
              <span className="field-label">{t("slideshow.subject")}</span>
              <input
                className="input"
                dir="auto"
                value={subject}
                maxLength={64}
                placeholder={t("slideshow.subject_placeholder")}
                onChange={(e) => setSubject(e.target.value)}
                onBlur={() => subject !== (v.settings.subject || "") && update({ subject })}
              />
              <span className="field-hint">{t("slideshow.subject_hint")}</span>
            </label>
          </section>
        </div>

        {/* ------------------------------------------------------------ preview + export */}
        <aside className="ss-side">
          <section className="panel ss-preview" aria-labelledby="ss-prev-h">
            <h2 id="ss-prev-h">{t("slideshow.preview")}</h2>
            <div className="ss-phone">
              {v.preview && !pJob ? (
                <video key={v.preview.stamp ?? ""} src={slideUrls.preview(id, v.preview.stamp)} controls playsInline loop
                  aria-label={t("slideshow.preview")} />
              ) : n > 0 ? (
                <img src={slideUrls.thumb(id, v.photos[0].id)} alt="" className="ss-phone-poster" />
              ) : (
                <span className="ss-phone-empty muted"><Icon name="image" size={28} /></span>
              )}
              {pJob && (
                <div className="ss-phone-busy">
                  <span className="spinner" />
                  <span>{t("slideshow.previewing")}</span>
                </div>
              )}
            </div>
            <p className="ss-length">
              {t("slideshow.length", { s: secs(tl.total, num) })}
              <span className="muted">
                {" "}
                {v.settings.outro
                  ? t("slideshow.length_parts_outro", { n: num(n), s: secs(v.settings.seconds, num), o: secs(v.limits.outro_s, num) })
                  : t("slideshow.length_parts", { n: num(n), s: secs(v.settings.seconds, num) })}
              </span>
            </p>
            {v.preview && !v.preview.fresh && !pJob && <p className="field-hint">{t("slideshow.preview_old")}</p>}
            {pLast?.status === "error" && pLast.error && !pJob && (
              <p className="field-hint ss-err" role="alert">{pLast.error.message}</p>
            )}
            <button type="button" className="btn" disabled={!v.ready || !!pJob} onClick={() => runJob("preview")}>
              <Icon name="play" size={14} /> {v.preview ? t("slideshow.preview_again") : t("slideshow.make_preview")}
            </button>
            {need > 0 && <p className="field-hint">{t("slideshow.need_more", { n: need })}</p>}
          </section>

          <section className="panel ss-export" aria-labelledby="ss-exp-h">
            <h2 id="ss-exp-h">{t("slideshow.export")}</h2>
            <p className="ss-music">
              <Icon name="music" size={14} /> {t("slideshow.no_music")}
            </p>
            {eJob ? (
              <div className="ss-progress">
                <ProgressBar value={eJob.status === "running" ? eJob.progress : null} label={t("slideshow.exporting")} />
                <span className="muted">
                  {eJob.status === "queued" ? t("job.waiting") : t("slideshow.exporting")}
                  {eJob.progress != null && eJob.status === "running" ? ` ${num(Math.round(eJob.progress * 100))}%` : ""}
                </span>
              </div>
            ) : (
              <button type="button" className="btn btn-primary btn-lg ss-export-btn" disabled={!v.ready} onClick={() => runJob("export")}>
                <Icon name="film" /> {v.export ? t("slideshow.export_again") : t("slideshow.export_btn")}
              </button>
            )}
            {eLast?.status === "error" && eLast.error && !eJob && (
              <div className="notice notice-danger" role="alert">
                <Icon name="alert" />
                <div>
                  <div className="notice-title">{eLast.error.message}</div>
                  {eLast.error.hint && <div className="muted ss-err-hint">{eLast.error.hint}</div>}
                </div>
              </div>
            )}
            {v.export && !eJob && (
              <div className="ss-done">
                <div className="ss-done-line">
                  <Icon name="check" size={16} />
                  <span>
                    {t("slideshow.ready", {
                      s: secs(v.export.duration, num),
                      size: fmtBytes(v.export.size_bytes),
                    })}
                  </span>
                </div>
                {!v.export.fresh && <p className="field-hint">{t("slideshow.export_old")}</p>}
                <div className="ss-done-actions">
                  <button type="button" className="btn" onClick={() => doSave("save")} disabled={!!saving}>
                    <Icon name="download" size={14} /> {t("slideshow.save")}
                  </button>
                  {meta?.is_local !== false && (
                    <button type="button" className="btn" onClick={() => doSave("open")} disabled={!!saving}>
                      <Icon name="file" size={14} /> {t("slideshow.open_folder")}
                    </button>
                  )}
                  <a className="btn btn-primary" href={href.share(id)}>
                    <Icon name="upload" size={14} /> {t("slideshow.share")}
                  </a>
                </div>
                {(saved || v.export.folder) && (
                  <p className="field-hint ss-folder" dir="ltr">{saved || v.export.folder}</p>
                )}
                <p className="field-hint">{t("slideshow.share_hint")}</p>
                {v.share?.kind === "shared" && (
                  <p className="ss-shared"><span className="chip chip-success">{t("slideshow.row_shared")}</span></p>
                )}
              </div>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
