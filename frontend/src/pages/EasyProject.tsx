import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  easyApi,
  urls,
  type EasyClip,
  type EasyUploadResult,
  type EasyView,
  type Mode,
  type UploadWhen,
} from "../api";
import { EasyProgress, ModeChip } from "../components/Easy";
import { CoverStudio } from "../components/CoverStudio";
import { Icon } from "../components/Icons";
import { Modal, ProgressBar, Toggle } from "../components/ui";
import { ConnectPrompt } from "../components/YoutubeConnect";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { useMeta } from "../meta";
import { href } from "../router";
import { useToast } from "../toast";
import { useUiMode } from "../uimode";

const LOCK_TOLD = "sc-easy-lock-told";

function once(key: string): boolean {
  try {
    if (localStorage.getItem(key)) return false;
    localStorage.setItem(key, "1");
  } catch {
    /* private mode: say it every time */
  }
  return true;
}

function fmtWhen(iso: string | null | undefined, lang: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

/** Easy mode: one project = progress, then the best clips with two big buttons each. */
export default function EasyProject({ id }: { id: string }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const { finishedTick } = useJobs();
  const { settings, update } = useUiMode();
  const [view, setView] = useState<EasyView | null>(null);
  const [missing, setMissing] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState<EasyClip | null>(null);
  const [connectFor, setConnectFor] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<Record<string, "upload" | "download">>({});
  const [tracked, setTracked] = useState<Record<string, string>>({}); // cid -> title of uploads to report
  const [allBusy, setAllBusy] = useState(false);
  const prepared = useRef(false);
  const when: UploadWhen = settings?.upload_when ?? "now";

  const load = useCallback(async () => {
    try {
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

  // Poll while anything moves (progress bars); slowly otherwise (views, schedule).
  const moving =
    !!view &&
    (view.state === "working" ||
      view.clips.some((c) => ["rendering", "queued"].includes(c.render.status) || ["uploading", "queued_uploading", "rendering"].includes(c.upload.step ?? "")) ||
      Object.keys(tracked).length > 0);
  useEffect(() => {
    const ms = moving ? 1500 : 15000;
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), ms);
    return () => window.clearInterval(iv);
  }, [moving, load]);

  // Uploads this screen started: "Uploaded" + "Open on YouTube" when they are up.
  useEffect(() => {
    if (!view) return;
    const done: string[] = [];
    for (const [cid, title] of Object.entries(tracked)) {
      const c = view.clips.find((x) => x.id === cid);
      if (!c) continue;
      if (c.upload.status === "published" || c.upload.status === "locked" || (c.upload.status === "scheduled" && c.upload.step === "uploaded")) {
        done.push(cid);
        const url = c.upload.url;
        toast({
          kind: "ok",
          text: c.upload.status === "scheduled" ? t("easy.toast_planned_up", { title }) : t("easy.toast_uploaded", { title }),
          action: url ? { label: t("easy.open_youtube"), run: () => window.open(url, "_blank", "noopener") } : undefined,
        });
      } else if (c.upload.status === "failed") {
        done.push(cid);
        toast({ kind: "err", text: t("easy.toast_upload_failed", { title }), hint: c.upload.error?.message });
      }
    }
    if (done.length) setTracked((cur) => Object.fromEntries(Object.entries(cur).filter(([k]) => !done.includes(k))));
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const tellLock = () => {
    if (view.youtube.lock === "locked" && once(LOCK_TOLD)) {
      toast({ kind: "info", text: t("easy.lock_title"), hint: t("easy.lock_body") });
    }
  };

  const report = (r: EasyUploadResult, c: EasyClip | undefined) => {
    const title = c?.title ?? "";
    if (r.status === "uploading") {
      if (c) setTracked((cur) => ({ ...cur, [c.id]: title }));
      toast({ kind: "info", text: t("easy.toast_uploading", { title }) });
    } else if (r.status === "scheduled") {
      toast({
        kind: "ok",
        text: t("easy.toast_planned", { title, when: fmtWhen(r.publish_at, lang) }),
        hint: r.today_full ? t("easy.today_full", { n: view.daily_limit }) : null,
      });
    } else if (r.status === "published") {
      toast({ kind: "ok", text: t("easy.already_up"), action: r.url ? { label: t("easy.open_youtube"), run: () => window.open(r.url!, "_blank", "noopener") } : undefined });
    } else if (r.status === "error") {
      toast({ kind: "err", text: r.error || t("common.error") });
    }
  };

  const uploadClips = async (cids: string[]) => {
    if (!cids.length) return;
    if (!view.youtube.connected) {
      setConnectFor(cids);
      return;
    }
    setBusy((b) => ({ ...b, ...Object.fromEntries(cids.map((c) => [c, "upload" as const])) }));
    try {
      if (cids.length === 1) {
        report(await easyApi.upload(id, cids[0], when), view.clips.find((c) => c.id === cids[0]));
      } else {
        const res = await easyApi.uploadMany(cids.map((c) => ({ project_id: id, clip_id: c })), when);
        for (const r of res.results) report(r, view.clips.find((c) => c.id === r.clip_id));
        setSelected([]);
      }
      tellLock();
      load();
    } catch (e) {
      if (e instanceof ApiError && e.code === "not_connected") setConnectFor(cids);
      else if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy((b) => Object.fromEntries(Object.entries(b).filter(([k]) => !cids.includes(k))));
    }
  };

  const download = async (c: EasyClip) => {
    if (!meta?.is_local) {
      // another device (phone / LAN): the browser saves the video itself
      window.location.href = urls.clipDownload(id, c.id);
      return;
    }
    setBusy((b) => ({ ...b, [c.id]: "download" }));
    try {
      const r = await easyApi.download(id, c.id);
      toast({ kind: "ok", text: t("easy.toast_saved"), hint: r.folder });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy((b) => Object.fromEntries(Object.entries(b).filter(([k]) => k !== c.id)));
    }
  };

  const downloadAll = async () => {
    setAllBusy(true);
    try {
      const r = await easyApi.downloadAll(id, false);
      toast({ kind: "ok", text: t("easy.toast_saved_all", { n: r.count ?? 0 }), hint: r.folder });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setAllBusy(false);
    }
  };

  const discard = async (c: EasyClip) => {
    try {
      setView(await easyApi.discard(id, c.id));
      setSelected((s) => s.filter((x) => x !== c.id));
      toast({ kind: "ok", text: t("easy.discarded") });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const changeMode = async (m: Mode | "auto") => {
    if (m === "auto" || m === view.mode) return;
    try {
      setView(await easyApi.setMode(id, m));
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const ready = view.clips.filter((c) => c.render.status === "ready");
  const toggleSel = (cid: string) => setSelected((s) => (s.includes(cid) ? s.filter((x) => x !== cid) : [...s, cid]));
  const working = view.state === "working";

  return (
    <main className="page ez-page">
      <a className="ez-back" href={href.library}>
        <Icon name="chevron-left" size={16} className="flip-rtl" /> {t("easy.new_video")}
      </a>
      <div className="ez-head">
        <div className="ez-head-text">
          <h1 className="ez-title" dir="auto">
            {view.title}
          </h1>
          <div className="ez-head-meta">
            <ModeChip value={view.mode} onChange={changeMode} auto={view.mode_auto} disabled={working} />
            {view.duration > 0 && <span className="muted">{fmtTime(view.duration)}</span>}
          </div>
        </div>
        {ready.length > 1 && (
          <button className="btn btn-lg" onClick={downloadAll} disabled={allBusy}>
            {allBusy ? <span className="spinner" /> : <Icon name="download" />}
            {t("easy.download_all")}
          </button>
        )}
      </div>

      {working && <EasyProgress steps={view.steps} eta={view.eta_seconds} compact={view.clips.length > 0} />}

      {view.state === "error" && view.error && (
        <div className="notice notice-danger ez-error" role="alert">
          <Icon name="alert" />
          <div style={{ flex: 1 }}>
            <div className="notice-title">{t("easy.failed")}</div>
            <div className="muted">{view.error.message}</div>
          </div>
          <button className="btn" onClick={() => easyApi.retry(id).then(setView).catch(() => {})}>
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

      {view.clips.length > 0 && (
        <>
          <h2 className="ez-section-title">{t("easy.best_clips")}</h2>
          <ul className="ez-grid" aria-label={t("easy.best_clips")}>
            {view.clips.map((c) => (
              <ClipCard
                key={c.id}
                pid={id}
                c={c}
                when={when}
                onWhen={(w) => update({ upload_when: w })}
                selected={selected.includes(c.id)}
                onSelect={() => toggleSel(c.id)}
                busy={busy[c.id]}
                onUpload={() => uploadClips([c.id])}
                onDownload={() => download(c)}
                onEdit={() => setEditing(c)}
                onDiscard={() => discard(c)}
              />
            ))}
          </ul>
          {view.total > view.shown && (
            <div className="ez-more">
              <button className="btn btn-lg" onClick={() => easyApi.more(id).then(setView).catch(() => {})}>
                <Icon name="plus" /> {t("easy.show_more")}
              </button>
            </div>
          )}
        </>
      )}

      {selected.length > 0 && (
        <div className="ez-selbar" role="region" aria-label={t("easy.selection")}>
          <span>{t("easy.selected", { n: selected.length })}</span>
          <button className="btn btn-ghost" onClick={() => setSelected([])}>
            {t("easy.clear_selection")}
          </button>
          <button className="btn btn-primary btn-lg" onClick={() => uploadClips(selected.filter((s) => ready.some((r) => r.id === s)))}>
            <Icon name="upload" /> {t("easy.upload_selected")}
          </button>
        </div>
      )}

      {editing && (
        <EditSheet
          pid={id}
          clip={view.clips.find((c) => c.id === editing.id) ?? editing}
          musicAvailable={view.music_available}
          onClose={() => setEditing(null)}
          onSaved={(v) => {
            setView(v);
            setEditing(null);
          }}
        />
      )}

      {connectFor && (
        <Modal title={t("easy.connect_title")} onClose={() => setConnectFor(null)}>
          <p style={{ marginTop: 0 }}>{t("easy.connect_body")}</p>
          <ConnectPrompt
            onConnected={() => {
              const cids = connectFor;
              setConnectFor(null);
              setView((v) => (v ? { ...v, youtube: { ...v.youtube, connected: true } } : v));
              // continue the upload by itself
              window.setTimeout(() => {
                easyApi.view(id).then((v) => {
                  setView(v);
                  if (cids) {
                    const run = cids.length === 1 ? easyApi.upload(id, cids[0], when).then((r) => [{ ...r, clip_id: cids[0] }]) : easyApi.uploadMany(cids.map((c) => ({ project_id: id, clip_id: c })), when).then((r) => r.results);
                    run
                      .then((rs) => {
                        for (const r of rs) report(r, v.clips.find((c) => c.id === r.clip_id));
                        load();
                      })
                      .catch((e) => e instanceof ApiError && toast({ kind: "err", text: e.message, hint: e.hint }));
                  }
                });
              }, 50);
            }}
          />
        </Modal>
      )}
    </main>
  );
}

// ---------------------------------------------------------------- one clip

function ClipCard({
  pid,
  c,
  when,
  onWhen,
  selected,
  onSelect,
  busy,
  onUpload,
  onDownload,
  onEdit,
  onDiscard,
}: {
  pid: string;
  c: EasyClip;
  when: UploadWhen;
  onWhen: (w: UploadWhen) => void;
  selected: boolean;
  onSelect: () => void;
  busy?: "upload" | "download";
  onUpload: () => void;
  onDownload: () => void;
  onEdit: () => void;
  onDiscard: () => void;
}) {
  const { t, num, lang } = useI18n();
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const r = c.render;
  const ok = r.status === "ready" && r.has_video;
  const up = c.upload;
  const uploading = up.step === "uploading" || up.step === "queued_uploading" || busy === "upload";
  const titleId = `ez-t-${c.id}`;

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenu(false);
    const key = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", key);
    };
  }, [menu]);

  let upPart: JSX.Element;
  if (up.status === "published" || up.status === "locked") {
    upPart = (
      <div className="ez-up-state ez-up-live">
        <Icon name="check" size={18} />
        <span>{up.status === "locked" ? t("easy.live_private") : t("easy.live")}</span>
        {up.url && (
          <a className="btn btn-primary ez-big" href={up.url} target="_blank" rel="noreferrer">
            <Icon name="eye" /> {t("easy.open_youtube")}
          </a>
        )}
      </div>
    );
  } else if (uploading) {
    upPart = (
      <div className="ez-up-state">
        <span className="ez-up-line">
          <span className="spinner" /> {up.progress != null ? t("easy.uploading_pct", { p: num(Math.round(up.progress * 100)) }) : t("easy.uploading")}
        </span>
        <ProgressBar value={up.progress} label={t("easy.uploading")} />
      </div>
    );
  } else if (up.status === "scheduled") {
    upPart = (
      <div className="ez-up-state ez-up-planned">
        <Icon name="calendar" size={18} />
        <span>{t("easy.planned_for", { when: fmtWhen(up.publish_at || up.date, lang) })}</span>
      </div>
    );
  } else {
    upPart = (
      <>
        {up.status === "failed" && (
          <p className="ez-up-error" role="alert">
            <Icon name="alert" size={15} /> {up.error?.message || t("easy.toast_upload_failed", { title: "" })}
          </p>
        )}
        <button className="btn btn-primary ez-big" disabled={!ok || !!busy} onClick={onUpload}>
          <Icon name="upload" /> {t("easy.upload_youtube")}
        </button>
        <div className="ez-when" role="radiogroup" aria-label={t("easy.when_label")}>
          {(["now", "auto"] as UploadWhen[]).map((w) => (
            <button key={w} type="button" role="radio" aria-checked={when === w} onClick={() => onWhen(w)}>
              {t(`easy.when_${w}`)}
            </button>
          ))}
        </div>
      </>
    );
  }

  return (
    <li className={`ez-card${selected ? " selected" : ""}`} aria-labelledby={titleId}>
      <div className="ez-video">
        {ok ? (
          <video
            src={urls.clip(pid, c.id, r.stamp ?? "")}
            controls
            playsInline
            preload="metadata"
            aria-label={c.title}
          />
        ) : (
          <div className="ez-video-wait">
            {r.status === "error" ? (
              <>
                <Icon name="alert" size={26} />
                <span>{t("easy.render_failed")}</span>
              </>
            ) : (
              <>
                <span className="spinner" />
                <span>{t("easy.preparing")}</span>
                {r.progress != null && <ProgressBar value={r.progress} label={t("easy.preparing")} />}
              </>
            )}
          </div>
        )}
        <label className="ez-check" title={t("easy.select")}>
          <input type="checkbox" checked={selected} onChange={onSelect} disabled={!ok} aria-label={t("easy.select_clip", { title: c.title })} />
        </label>
        <span className="ez-dur mono">{fmtTime(c.duration)}</span>
      </div>
      <div className="ez-card-body">
        {c.viral_label && (
          <span className={`ez-viral ez-viral-${c.viral_label}`}>
            <Icon name="sparkles" size={13} /> {t("easy.viral", { label: t(`publish.label.${c.viral_label}`) })}
          </span>
        )}
        <h3 className="ez-card-title" id={titleId} dir="auto">
          {c.title}
        </h3>
        <div className="ez-actions">
          {upPart}
          <button className="btn ez-big" disabled={!ok || !!busy} onClick={onDownload}>
            {busy === "download" ? <span className="spinner" /> : <Icon name="download" />} {t("easy.download_pc")}
          </button>
        </div>
        <div className="ez-card-foot">
          <button className="link-btn" onClick={onEdit} disabled={up.status === "published" || uploading}>
            <Icon name="wand" size={14} /> {t("easy.edit")}
          </button>
          <div className="ez-menu" ref={menuRef}>
            <button
              className="btn btn-ghost icon-btn"
              aria-label={t("easy.more_actions")}
              aria-haspopup="menu"
              aria-expanded={menu}
              onClick={() => setMenu((m) => !m)}
            >
              <span aria-hidden="true">…</span>
            </button>
            {menu && (
              <div className="ez-menu-pop" role="menu">
                <button
                  role="menuitem"
                  onClick={() => {
                    setMenu(false);
                    onDiscard();
                  }}
                  disabled={up.status === "published" || up.status === "scheduled"}
                >
                  <Icon name="trash" size={15} /> {t("easy.discard")}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------- the simple edit sheet

function EditSheet({
  pid,
  clip,
  musicAvailable,
  onClose,
  onSaved,
}: {
  pid: string;
  clip: EasyClip;
  musicAvailable: boolean;
  onClose: () => void;
  onSaved: (v: EasyView) => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const ideas = Array.from(new Set([clip.title, ...clip.titles].filter(Boolean)));
  const [title, setTitle] = useState(clip.title);
  const [start, setStart] = useState(clip.start);
  const [end, setEnd] = useState(clip.end);
  const [subs, setSubs] = useState(clip.prefs.subtitles);
  const [music, setMusic] = useState(clip.prefs.music);
  const [saving, setSaving] = useState(false);
  const [srcOk, setSrcOk] = useState(true);
  const vid = useRef<HTMLVideoElement>(null);
  const lo = clip.bounds.start;
  const hi = clip.bounds.end;
  const len = end - start;
  const trimmed = Math.abs(start - clip.start) > 0.04 || Math.abs(end - clip.end) > 0.04;
  const bad = trimmed && (len < 3 || len > 180);

  const seek = (s: number) => {
    const v = vid.current;
    if (v && Number.isFinite(s)) v.currentTime = s;
  };

  const save = async () => {
    setSaving(true);
    try {
      const body: Parameters<typeof easyApi.edit>[2] = {};
      if (title.trim() !== clip.title) body.title = title.trim();
      if (subs !== clip.prefs.subtitles) body.subtitles = subs;
      if (music !== clip.prefs.music) body.music = music;
      if (trimmed) {
        body.start = start;
        body.end = end;
      }
      onSaved(await easyApi.edit(pid, clip.id, body));
      toast({ kind: "ok", text: body.start != null || body.subtitles != null || body.music != null ? t("easy.saved_rerender") : t("common.saved") });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setSaving(false);
    }
  };

  const pct = (v: number) => ((v - lo) / Math.max(0.1, hi - lo)) * 100;

  return (
    <Modal
      title={t("easy.edit_title")}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" onClick={save} disabled={saving || bad || !title.trim()}>
            {saving && <span className="spinner" />} {t("common.save")}
          </button>
        </>
      }
    >
      <fieldset className="ez-field">
        <legend>{t("easy.edit_pick_title")}</legend>
        <div className="ez-titles">
          {ideas.map((x) => (
            <label key={x} className={`ez-title-opt${title === x ? " on" : ""}`}>
              <input type="radio" name="ez-title" checked={title === x} onChange={() => setTitle(x)} />
              <span dir="auto">{x}</span>
            </label>
          ))}
        </div>
        <label className="field" style={{ marginTop: 10 }}>
          <span className="field-label">{t("easy.edit_own_title")}</span>
          <input className="input" dir="auto" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
        </label>
      </fieldset>

      <fieldset className="ez-field">
        <legend>{t("easy.edit_trim")}</legend>
        {srcOk && (
          <video
            ref={vid}
            className="ez-trim-video"
            src={`${urls.source(pid)}#t=${start.toFixed(1)}`}
            preload="metadata"
            muted
            playsInline
            controls
            onError={() => setSrcOk(false)}
            aria-label={t("easy.edit_trim")}
          />
        )}
        <div className="ez-trim">
          <div className="ez-trim-track" aria-hidden="true">
            <span style={{ insetInlineStart: `${pct(start)}%`, width: `${pct(end) - pct(start)}%` }} />
          </div>
          <input
            type="range"
            min={lo}
            max={hi}
            step={0.1}
            value={start}
            aria-label={t("easy.trim_start")}
            onChange={(e) => {
              const v = Math.min(Number(e.target.value), end - 3);
              setStart(v);
              seek(v);
            }}
          />
          <input
            type="range"
            min={lo}
            max={hi}
            step={0.1}
            value={end}
            aria-label={t("easy.trim_end")}
            onChange={(e) => {
              const v = Math.max(Number(e.target.value), start + 3);
              setEnd(v);
              seek(v);
            }}
          />
        </div>
        <div className="ez-trim-times mono">
          <span>{fmtTime(start)}</span>
          <span className={bad ? "danger" : "muted"}>{t("easy.trim_length", { s: num(len, 1) })}</span>
          <span>{fmtTime(end)}</span>
        </div>
        <button
          type="button"
          className="link-btn"
          onClick={() => {
            setStart(clip.found.start);
            setEnd(clip.found.end);
          }}
        >
          {t("easy.trim_reset")}
        </button>
      </fieldset>

      <div className="ez-toggles">
        <div className="toggle-line">
          <span>
            <b>{t("easy.subtitles")}</b>
          </span>
          <Toggle checked={subs} onChange={setSubs} label={t("easy.subtitles")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("easy.music")}</b>
            {!musicAvailable && <span className="muted ez-hint">{t("easy.music_none")}</span>}
          </span>
          <Toggle checked={music && musicAvailable} onChange={(v) => musicAvailable && setMusic(v)} label={t("easy.music")} />
        </div>
      </div>

      <fieldset className="ez-field">
        <legend>{t("cover_ai.easy_title")}</legend>
        <CoverStudio pid={pid} cid={clip.id} frames={["tall", "wide"]} text={title} lang={null} compact />
      </fieldset>
    </Modal>
  );
}
