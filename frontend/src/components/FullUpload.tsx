import { useEffect, useMemo, useState } from "react";
import { fullApi, type FullDraft, type FullUploadView } from "../api";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Modal, ProgressBar, Toggle } from "./ui";

/** ISO (UTC) -> the value of an <input type="datetime-local"> in this computer's time. */
function toLocalInput(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fromLocalInput(v: string): string {
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
}

const CATEGORIES = [
  ["20", "full.cat_gaming"],
  ["27", "full.cat_education"],
  ["10", "full.cat_music"],
  ["24", "full.cat_entertainment"],
  ["22", "full.cat_people"],
] as const;

/** The project toolbar button: the full video's state, opens the confirm screen. */
export function FullUploadButton({ projectId, canPrepare }: { projectId: string; canPrepare: boolean }) {
  const { t } = useI18n();
  const { finishedTick } = useJobs();
  const [v, setV] = useState<FullUploadView | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    fullApi.view(projectId).then(setV).catch(() => setV(null));
  }, [projectId, finishedTick, open]);
  if (!v || (!v.status && !canPrepare)) return null;
  const ready = v.status === "review";
  const label =
    v.status === "scheduled" || v.status === "published"
      ? t("full.button_done")
      : ready
        ? t("full.button_review")
        : t("full.button");
  return (
    <>
      <button
        className={`btn btn-sm${ready ? " btn-gold" : ""}`}
        data-testid="full-video"
        onClick={() => setOpen(true)}
        title={t("full.button_hint")}
      >
        <Icon name="upload" />
        {label}
      </button>
      {open && <FullUploadDialog projectId={projectId} onClose={() => setOpen(false)} />}
    </>
  );
}

export function FullUploadDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick } = useJobs();
  const [v, setV] = useState<FullUploadView | null>(null);
  const [d, setD] = useState<FullDraft | null>(null);
  const [tags, setTags] = useState("");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const prepJob = jobs.find((j) => j.kind === "full_prepare" && j.project_id === projectId && isActive(j));
  const upJob = jobs.find((j) => j.kind === "full_upload" && j.project_id === projectId && isActive(j));
  const fill = (x: FullUploadView) => {
    setV(x);
    if (x.draft) {
      setD(x.draft);
      setTags(x.draft.tags.join(", "));
      setWhen(toLocalInput(x.draft.publish_at));
    }
  };
  useEffect(() => {
    fullApi.view(projectId).then(fill).catch(() => {});
  }, [projectId, finishedTick]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmtWhen = useMemo(
    () => (iso?: string) =>
      iso ? new Date(iso).toLocaleString(lang, { dateStyle: "full", timeStyle: "short" }) : "",
    [lang],
  );
  const err = (e: any) => toast({ kind: "err", text: e.message, hint: e.hint });
  const edits = (): Partial<FullDraft> | null => {
    if (!d) return null;
    const publish_at = fromLocalInput(when);
    return {
      title: d.title,
      description: d.description,
      tags: tags
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      category: d.category,
      use_thumbnail: d.use_thumbnail !== false,
      ...(publish_at ? { publish_at } : {}),
    };
  };
  const prepare = async (force = false) => {
    try {
      await fullApi.prepare(projectId, force);
      fill(await fullApi.view(projectId));
    } catch (e) {
      err(e);
    }
  };
  const save = async () => {
    const e = edits();
    if (!e) return;
    setBusy(true);
    try {
      fill(await fullApi.save(projectId, e));
      toast({ kind: "ok", text: t("common.saved") });
    } catch (x) {
      err(x);
    } finally {
      setBusy(false);
    }
  };
  const upload = async () => {
    const e = edits();
    if (!e) return;
    setBusy(true);
    try {
      await fullApi.upload(projectId, e);
      toast({ kind: "ok", text: t("full.started") });
      fill(await fullApi.view(projectId));
    } catch (x) {
      err(x);
    } finally {
      setBusy(false);
    }
  };
  const skip = async () => {
    try {
      fill(await fullApi.skip(projectId));
      onClose();
    } catch (x) {
      err(x);
    }
  };

  const status = v?.status ?? null;
  const editable = status === "review" || status === "failed";
  const footer = !v ? null : editable && d ? (
    <>
      <button className="btn btn-ghost btn-sm" onClick={skip} disabled={busy}>
        {t("full.skip")}
      </button>
      <button className="btn btn-sm" onClick={save} disabled={busy}>
        {t("common.save")}
      </button>
      <button className="btn btn-primary btn-sm" onClick={upload} disabled={busy || !!upJob || !v.connected}>
        <Icon name="upload" />
        {t("full.upload")}
      </button>
    </>
  ) : status === null || status === "skipped" || (status === "wanted" && !prepJob) ? (
    <button className="btn btn-gold btn-sm" onClick={() => prepare(false)} disabled={!!prepJob}>
      <Icon name="sparkles" />
      {t("full.prepare")}
    </button>
  ) : null;

  return (
    <Modal title={t("full.title")} onClose={onClose} wide footer={footer}>
      {!v ? null : (
        <div style={{ display: "grid", gap: 14 }}>
          <p className="muted" style={{ margin: 0 }}>
            {t("full.desc")}
          </p>
          {!v.connected && (
            <div className="notice notice-warn" role="status">
              <Icon name="alert" />
              <div>{t("full.not_connected")}</div>
            </div>
          )}
          {(status === "preparing" || prepJob) && (
            <div className="notice" role="status">
              <span className="spinner" />
              <div>{t("full.preparing")}</div>
            </div>
          )}
          {status === "wanted" && !prepJob && <p className="field-hint">{t("full.wanted")}</p>}
          {status === "skipped" && <p className="field-hint">{t("full.skipped")}</p>}
          {status === "failed" && v.error && (
            <div className="notice notice-danger" role="alert">
              <Icon name="alert" />
              <div>
                <div className="notice-title">{v.error.message}</div>
                {v.error.hint && <div className="muted">{v.error.hint}</div>}
                <div className="muted">{t("full.failed_hint")}</div>
              </div>
            </div>
          )}
          {upJob && (
            <div style={{ display: "grid", gap: 6 }} role="status">
              <span>
                {upJob.stage === "retrying" ? t("full.retrying") : t("full.uploading")}
                {upJob.progress != null && `, ${Math.round(upJob.progress * 100)}%`}
              </span>
              <ProgressBar value={upJob.progress ?? null} />
              <span className="field-hint">{t("full.resume_hint")}</span>
            </div>
          )}
          {(status === "scheduled" || status === "published") && v.upload && (
            <div className="notice" role="status">
              <Icon name="check" />
              <div style={{ display: "grid", gap: 4 }}>
                <div className="notice-title">
                  {status === "published" ? t("full.published") : t("full.scheduled", { when: fmtWhen(v.upload.publish_at) })}
                </div>
                <a href={v.upload.url} target="_blank" rel="noreferrer" dir="ltr">
                  {v.upload.url}
                </a>
                {v.needs_studio && (
                  <div>
                    {t("full.studio_note")}{" "}
                    <a href={v.upload.studio_url} target="_blank" rel="noreferrer">
                      {t("full.open_studio")}
                    </a>
                  </div>
                )}
                {v.thumbnail_error && <div className="muted">{t("full.thumb_failed", { why: v.thumbnail_error })}</div>}
                <div className="muted">{t("full.shorts_link")}</div>
              </div>
            </div>
          )}
          {editable && d && (
            <>
              <label className="field">
                <span className="field-label">
                  {t("full.f_title")} <span className="muted mono">{d.title.length}/100</span>
                </span>
                <input
                  className="input"
                  dir="auto"
                  maxLength={100}
                  value={d.title}
                  onChange={(e) => setD({ ...d, title: e.target.value })}
                />
              </label>
              {d.titles.length > 1 && (
                <div className="full-alts">
                  {d.titles.slice(0, 6).map((x) => (
                    <button
                      key={x}
                      type="button"
                      className="full-alt"
                      aria-pressed={x === d.title}
                      onClick={() => setD({ ...d, title: x })}
                      dir="auto"
                    >
                      {x}
                    </button>
                  ))}
                </div>
              )}
              <label className="field">
                <span className="field-label">{t("full.f_description")}</span>
                <textarea
                  className="textarea"
                  dir="auto"
                  rows={12}
                  value={d.description}
                  onChange={(e) => setD({ ...d, description: e.target.value })}
                />
                <span className="field-hint">{t("full.desc_hint")}</span>
              </label>
              <label className="field">
                <span className="field-label">{t("full.f_tags")}</span>
                <input className="input" dir="auto" value={tags} onChange={(e) => setTags(e.target.value)} />
              </label>
              <div className="brand-grid">
                <label className="field">
                  <span className="field-label">{t("full.f_when")}</span>
                  <input
                    className="input"
                    type="datetime-local"
                    value={when}
                    onChange={(e) => setWhen(e.target.value)}
                  />
                  <span className="field-hint">{t("full.when_hint", { time: v.release_time })}</span>
                </label>
                <label className="field">
                  <span className="field-label">{t("full.f_category")}</span>
                  <select className="select" value={d.category} onChange={(e) => setD({ ...d, category: e.target.value })}>
                    {CATEGORIES.map(([id, key]) => (
                      <option key={id} value={id}>
                        {t(key)}
                      </option>
                    ))}
                  </select>
                  <span className="field-hint">{t("full.not_for_kids")}</span>
                </label>
              </div>
              {d.thumbnail && (
                <div className="field">
                  <span className="field-label">{t("full.f_thumb")}</span>
                  <img
                    src={fullApi.thumbnail(projectId, d.thumbnail)}
                    alt={t("full.thumb_alt")}
                    style={{ width: "100%", maxWidth: 420, aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 8 }}
                  />
                  <div className="toggle-line">
                    <span>{t("full.use_thumb")}</span>
                    <Toggle
                      checked={d.use_thumbnail !== false}
                      onChange={(x) => setD({ ...d, use_thumbnail: x })}
                      label={t("full.use_thumb")}
                    />
                  </div>
                </div>
              )}
              <p className="field-hint" style={{ margin: 0 }}>
                {t("full.limits", { n: v.daily_limit })}
                {v.today > 0 && ` ${t("full.today_used")}`}
              </p>
              {status === "review" && (
                <button className="btn btn-ghost btn-sm" style={{ justifySelf: "start" }} onClick={() => prepare(true)} disabled={!!prepJob}>
                  <Icon name="refresh" />
                  {t("full.rewrite")}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
