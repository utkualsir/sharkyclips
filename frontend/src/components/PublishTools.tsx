import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  api,
  urls,
  type CoverInfo,
  type CoverKind,
  type LibraryRow,
  type Playlist,
  type Privacy,
  type PublishMeta,
  type PublishSettings,
  type PublishSetup as SetupData,
  type ScheduleResult,
  type YoutubeLock,
} from "../api";
import { fmtTime } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { href } from "../router";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Markdown } from "./Shell";
import { Modal, Segmented, Toggle } from "./ui";

// ------------------------------------------------------------------ helpers

export function localInput(d: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function useWhen() {
  const { lang } = useI18n();
  return useMemo(() => {
    const full = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const time = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { hour: "2-digit", minute: "2-digit" });
    return { full: (iso: string) => full.format(new Date(iso)), time: (iso: string) => time.format(new Date(iso)) };
  }, [lang]);
}

function splitList(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

function tagChars(tags: string[]) {
  return tags.reduce((n, t, i) => n + t.length + (t.includes(" ") ? 2 : 0) + (i ? 1 : 0), 0);
}

const LANG_CODES = ["en", "tr", "de", "hu", "ru", "ar", "zh"];

// ------------------------------------------------------------------ lock banner + Google's checklist

const CHECKLIST = ["site", "domain", "consent", "scopes", "video", "oauth", "audit"] as const;

export function LockBanner({ lock, compact = false }: { lock: YoutubeLock | undefined; compact?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  if (!lock || lock.state === "unlocked") return null;
  return (
    <div className="notice notice-warn lock-banner" role="status">
      <Icon name="lock" />
      <div>
        <b>{t("pub.lock_title")}</b>{" "}
        {!compact && <p>{lock.state === "locked" ? t("pub.lock_seen") : t("pub.lock_unknown")}</p>}
        <button className="link-btn" onClick={() => setOpen(true)}>
          {t("pub.lock_checklist")}
        </button>
      </div>
      {open && createPortal(<VerificationDialog onClose={() => setOpen(false)} />, document.body)}
    </div>
  );
}

export function VerificationDialog({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const [done, setDone] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(localStorage.getItem("sc-verify-checklist") || "{}");
    } catch {
      return {};
    }
  });
  const [doc, setDoc] = useState<{ markdown: string; url: string } | null>(null);
  const [full, setFull] = useState(false);
  useEffect(() => {
    api.verificationGuide().then(setDoc).catch(() => {});
  }, []);
  const toggle = (k: string) => {
    const next = { ...done, [k]: !done[k] };
    setDone(next);
    try {
      localStorage.setItem("sc-verify-checklist", JSON.stringify(next));
    } catch {
      /* private mode */
    }
  };
  return (
    <Modal title={t("pub.verify_title")} onClose={onClose} wide footer={<button className="btn btn-primary" onClick={onClose}>{t("common.close")}</button>}>
      <p className="muted" style={{ marginTop: 0 }}>
        {t("pub.verify_lede")}
      </p>
      <ul className="checklist">
        {CHECKLIST.map((k) => (
          <li key={k}>
            <label>
              <input type="checkbox" checked={!!done[k]} onChange={() => toggle(k)} />
              <span>
                <b>{t(`pub.verify.${k}`)}</b>
                <span className="muted">{t(`pub.verify.${k}_body`)}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="field-hint">{t("pub.verify_auto")}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="btn btn-sm" onClick={() => setFull(!full)} disabled={!doc?.markdown}>
          <Icon name="file" />
          {full ? t("pub.verify_hide_doc") : t("pub.verify_show_doc")}
        </button>
        {doc?.url && (
          <a className="btn btn-sm btn-ghost" href={doc.url} target="_blank" rel="noreferrer">
            <Icon name="link" />
            docs/google-verification.md
          </a>
        )}
        <a className="btn btn-sm btn-ghost" href="https://support.google.com/youtube/contact/yt_api_form" target="_blank" rel="noreferrer">
          <Icon name="link" />
          {t("pub.verify_form")}
        </a>
      </div>
      {full && doc && (
        <div className="verify-doc" tabIndex={0} role="region" aria-label="docs/google-verification.md">
          <Markdown text={doc.markdown.replace(/^# [^\n]*\n/, "")} />
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ publish setup (one clip)

const COVER_KINDS: CoverKind[] = ["peak", "action", "face", "custom", "none"];
const CATEGORY_DEFAULT = "20";

export function PublishSetupDialog({
  projectId,
  clipId,
  onClose,
  onDone,
}: {
  projectId: string;
  clipId: string;
  onClose: () => void;
  onDone?: () => void;
}) {
  const { t, num, relTime } = useI18n();
  const when = useWhen();
  const toast = useToast();
  const [data, setData] = useState<SetupData | null>(null);
  const [meta, setMeta] = useState<PublishMeta | null>(null);
  const [covers, setCovers] = useState<CoverInfo | null>(null);
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null);
  const [newPl, setNewPl] = useState<string | null>(null);
  const [whenAt, setWhenAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [tagText, setTagText] = useState("");
  const [hashText, setHashText] = useState("");
  const [coverText, setCoverText] = useState("");
  const [thumbV, setThumbV] = useState(0);
  const thumbInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .publishSetup(projectId, clipId)
      .then((d) => {
        setData(d);
        setMeta(d.meta);
        setTagText(d.meta.tags.join(", "));
        setHashText(d.meta.hashtags.map((h) => `#${h}`).join(" "));
        setCoverText(d.meta.cover.text);
        const at = d.item?.publish_at ?? d.upload?.publish_at;
        if (at) setWhenAt(localInput(new Date(at)));
        if (d.youtube.connected) api.playlists().then((r) => setPlaylists(r.items)).catch(() => setPlaylists([]));
      })
      .catch((e) => {
        toast({ kind: "err", text: e.message, hint: e.hint });
        onClose();
      });
    api.covers(projectId, clipId).then(setCovers).catch(() => {});
  }, [projectId, clipId]); // eslint-disable-line react-hooks/exhaustive-deps

  // the cover preview follows the text after a short pause
  const [previewText, setPreviewText] = useState("");
  useEffect(() => {
    const id = window.setTimeout(() => setPreviewText(coverText), 450);
    return () => window.clearTimeout(id);
  }, [coverText]);

  if (!data || !meta) {
    return (
      <Modal title={t("pub.setup_title")} onClose={onClose} wide>
        <div className="skeleton-lines">
          {[70, 90, 55, 80].map((w) => (
            <div key={w} className="skeleton" style={{ width: `${w}%` }} />
          ))}
        </div>
      </Modal>
    );
  }

  const set = (patch: Partial<PublishMeta>) => setMeta({ ...meta, ...patch });
  const preset = data.presets.find((p) => p.id === meta.preset) ?? data.presets[0];
  const wide = preset?.frame === "wide";
  const live = data.upload;
  const liveScheduled = !!live?.publish_at && new Date(live.publish_at).getTime() > Date.now();
  const tooLong = preset?.max_seconds != null && data.clip.duration > preset.max_seconds + 0.05;
  const tags = splitList(tagText);
  const tagLen = tagChars(tags);
  const hashtags = hashText
    .split(/[\s,]+/)
    .map((h) => h.replace(/^#+/, "").trim())
    .filter(Boolean);

  const full = (): PublishMeta => ({ ...meta, tags, hashtags, cover: { ...meta.cover, text: coverText } });

  const save = async (): Promise<boolean> => {
    try {
      const r = await api.savePublish(projectId, clipId, full());
      setMeta(r.meta);
      if (r.applied === "youtube") toast({ kind: "ok", text: t("pub.saved_youtube") });
      return true;
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
      return false;
    }
  };
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const saveDraft = () =>
    run(async () => {
      if (await save()) {
        if (!live) toast({ kind: "ok", text: t("pub.saved") });
        onDone?.();
        onClose();
      }
    });
  const schedule = () =>
    run(async () => {
      if (!(await save())) return;
      if (live) {
        const r = await api.reschedule(projectId, clipId, new Date(whenAt).toISOString(), false);
        toast({ kind: "ok", text: t(r.moved ? "pub.moved_to" : "pub.scheduled_for", { when: when.full(r.publish_at) }) });
      } else {
        const r = await api.schedule({ clips: [{ project_id: projectId, clip_id: clipId, publish_at: new Date(whenAt).toISOString() }], mode: "manual" });
        const p = r.planned[0];
        if (!p) throw new Error(t(`pub.skip.${r.skipped[0]?.reason ?? "missing"}`));
        toast({ kind: "ok", text: t(p.moved ? "pub.moved_to" : "pub.scheduled_for", { when: when.full(p.publish_at) }) });
      }
      onDone?.();
      onClose();
    });
  const nextSlot = () =>
    run(async () => {
      const r = await api.schedule({ clips: [{ project_id: projectId, clip_id: clipId }], mode: "auto", dry_run: true });
      if (r.planned[0]) setWhenAt(localInput(new Date(r.planned[0].publish_at)));
    });
  const publishNow = () =>
    run(async () => {
      if (!(await save())) return;
      await api.publishNow(projectId, clipId);
      toast({ kind: "ok", text: t("pub.now_queued") });
      onDone?.();
      onClose();
    });
  const pickThumb = async (file: File | undefined) => {
    if (!file) return;
    try {
      await api.uploadThumbnail(projectId, clipId, file);
      set({ cover: { ...meta.cover, kind: "custom" } });
      setThumbV((v) => v + 1);
      setCovers(covers ? { ...covers, custom: true } : covers);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const createPlaylist = () =>
    run(async () => {
      const pl = await api.createPlaylist(newPl ?? "");
      setPlaylists([...(playlists ?? []), pl]);
      set({ playlist: { id: pl.id, title: pl.title } });
      setNewPl(null);
    });

  const coverAvailable = (k: CoverKind) => {
    if (k === "face") return !!covers?.face;
    if (k === "custom") return true;
    return true;
  };
  const coverSrc = (k: CoverKind) =>
    k === "custom"
      ? urls.thumbnail(projectId, clipId, "custom", thumbV)
      : urls.cover(projectId, clipId, k, wide ? "wide" : "tall", previewText, meta.language, thumbV);
  const canSchedule = !!whenAt && new Date(whenAt).getTime() > Date.now() + 14 * 60 * 1000;
  const limits = data.limits;

  return (
    <Modal
      title={t("pub.setup_title_n", { n: data.clip.rank })}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="export-sum">
            {data.youtube.connected ? (
              <span className={limits.quota.uploads_left < 1 ? "warn-text" : "muted"}>
                {t("pub.quota_left", { n: limits.quota.uploads_left })}
              </span>
            ) : (
              <span className="warn-text">{t("pub.not_connected_short")}</span>
            )}
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn" onClick={saveDraft} disabled={busy || !meta.title.trim() || tagLen > 500}>
            {live ? t("pub.save_youtube") : t("pub.save_draft")}
          </button>
          {(!live || liveScheduled) && (
            <button className="btn" onClick={publishNow} disabled={busy || !meta.title.trim() || tagLen > 500 || (!live && !data.youtube.connected)}>
              <Icon name="upload" />
              {t("pub.publish_now")}
            </button>
          )}
          {(!live || liveScheduled) && (
            <button className="btn btn-primary" onClick={schedule} disabled={busy || !canSchedule || !meta.title.trim() || tagLen > 500}>
              <Icon name="calendar" />
              {live ? t("pub.reschedule") : t("pub.schedule")}
            </button>
          )}
        </>
      }
    >
      <div className="pub-setup">
        {live && (
          <div className="notice">
            <Icon name="link" />
            <span>
              {liveScheduled ? t("pub.live_scheduled", { when: when.full(live.publish_at!) }) : t("pub.live_out")}{" "}
              <a href={live.url} target="_blank" rel="noreferrer">
                {live.url}
              </a>
            </span>
          </div>
        )}
        {!data.youtube.connected && (
          <div className="notice notice-warn">
            <Icon name="alert" />
            <span>
              {t("pub.plan_without_youtube")} <a href={`${href.settings}`}>{t("nav.settings")}</a>
            </span>
          </div>
        )}
        {data.youtube.connected && !data.youtube.manage && (
          <div className="notice notice-warn">
            <Icon name="alert" />
            <span>
              {t("pub.need_manage")} <a href={`${href.settings}`}>{t("nav.settings")}</a>
            </span>
          </div>
        )}
        <LockBanner lock={data.youtube.connected ? data.youtube.lock : undefined} compact />

        <div className="pub-cols">
          <div className="pub-col">
            <fieldset className="field">
              <legend className="field-label">
                {t("yt.title_label")} <span className="muted mono">{num(meta.title.length)}/100</span>
              </legend>
              {data.ai.titles.length > 0 && (
                <div className="title-picks" role="radiogroup" aria-label={t("pub.ai_titles")}>
                  {data.ai.titles.map((x) => (
                    <label key={x} className={`title-pick${meta.title === x ? " on" : ""}`}>
                      <input type="radio" name="pub-title" checked={meta.title === x} onChange={() => set({ title: x })} />
                      <span dir="auto">{x}</span>
                    </label>
                  ))}
                </div>
              )}
              <input
                className="input"
                dir="auto"
                value={meta.title}
                maxLength={100}
                aria-label={t("pub.own_title")}
                placeholder={t("pub.own_title")}
                onChange={(e) => set({ title: e.target.value })}
              />
            </fieldset>
            <label className="field">
              <span className="field-label">{t("yt.description")}</span>
              <textarea className="input" dir="auto" rows={4} value={meta.description} onChange={(e) => set({ description: e.target.value })} />
              {data.ai.description && meta.description !== data.ai.description && (
                <button type="button" className="link-btn field-hint" onClick={() => set({ description: data.ai.description })}>
                  {t("pub.use_ai")}
                </button>
              )}
            </label>
            <label className="field">
              <span className="field-label">{t("pub.hashtags")}</span>
              <input className="input" dir="auto" value={hashText} onChange={(e) => setHashText(e.target.value)} placeholder="#deltaforce #gaming" />
              <span className="field-hint">{t("pub.hashtags_hint")}</span>
            </label>
            <label className="field">
              <span className="field-label">
                {t("yt.tags")}{" "}
                <span className={`mono ${tagLen > 500 ? "warn-text" : "muted"}`}>{num(tagLen)}/500</span>
              </span>
              <textarea className="input" dir="auto" rows={2} value={tagText} onChange={(e) => setTagText(e.target.value)} />
              <span className="field-hint">
                {t("pub.tags_hint")}{" "}
                <button type="button" className="link-btn" onClick={() => setTagText(data.ai.tags.join(", "))}>
                  <Icon name="sparkles" size={12} /> {t("pub.tags_ai")}
                </button>
              </span>
            </label>
            <div className="export-two">
              <label className="field">
                <span className="field-label">{t("pub.category")}</span>
                <select className="select" value={meta.category || CATEGORY_DEFAULT} onChange={(e) => set({ category: e.target.value })}>
                  {data.categories.map((c) => (
                    <option key={c} value={c}>
                      {t(`pub.cat.${c}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">{t("pub.language")}</span>
                <select className="select" value={meta.language ?? ""} onChange={(e) => set({ language: e.target.value || null })}>
                  <option value="">{t("pub.language_none")}</option>
                  {LANG_CODES.map((c) => (
                    <option key={c} value={c}>
                      {UI_LANGUAGES.find((l) => l.code === c)?.name ?? c}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="export-two">
              <div className="field">
                <span className="field-label">{t("yt.kids")}</span>
                <Segmented<"no" | "yes">
                  value={meta.made_for_kids ? "yes" : "no"}
                  options={[
                    { value: "no", label: t("yt.kids_no") },
                    { value: "yes", label: t("yt.kids_yes") },
                  ]}
                  onChange={(v) => set({ made_for_kids: v === "yes" })}
                  label={t("yt.kids")}
                />
              </div>
              <div className="field">
                <span className="field-label">{t("yt.privacy")}</span>
                <Segmented<Privacy>
                  value={meta.privacy}
                  options={(["public", "unlisted", "private"] as Privacy[]).map((p) => ({ value: p, label: t(`yt.privacy.${p}`) }))}
                  onChange={(p) => set({ privacy: p })}
                  label={t("yt.privacy")}
                />
                <span className="field-hint">{t("pub.privacy_hint")}</span>
              </div>
            </div>
            <label className="field">
              <span className="field-label">{t("pub.playlist")}</span>
              {newPl === null ? (
                <select
                  className="select"
                  value={meta.playlist?.id ?? ""}
                  disabled={!data.youtube.connected}
                  onChange={(e) => {
                    if (e.target.value === "__new") return setNewPl("");
                    const pl = (playlists ?? []).find((p) => p.id === e.target.value);
                    set({ playlist: pl ? { id: pl.id, title: pl.title } : null });
                  }}
                >
                  <option value="">{t("pub.playlist_none")}</option>
                  {meta.playlist && !(playlists ?? []).some((p) => p.id === meta.playlist!.id) && (
                    <option value={meta.playlist.id}>{meta.playlist.title}</option>
                  )}
                  {(playlists ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
                  {data.youtube.manage && <option value="__new">{t("pub.playlist_new")}</option>}
                </select>
              ) : (
                <span className="inline-row">
                  <input className="input" dir="auto" autoFocus value={newPl} placeholder={t("pub.playlist_name")} onChange={(e) => setNewPl(e.target.value)} />
                  <button type="button" className="btn btn-sm btn-primary" disabled={!newPl.trim() || busy} onClick={createPlaylist}>
                    {t("pub.playlist_create")}
                  </button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setNewPl(null)}>
                    {t("common.cancel")}
                  </button>
                </span>
              )}
            </label>
          </div>

          <div className="pub-col">
            <fieldset className="field">
              <legend className="field-label">{t("pub.cover")}</legend>
              <div className={`cover-grid${wide ? " wide" : ""}`} role="radiogroup" aria-label={t("pub.cover")}>
                {COVER_KINDS.map((k) => {
                  const ok = coverAvailable(k);
                  const on = meta.cover.kind === k;
                  return (
                    <label key={k} className={`cover-opt${on ? " on" : ""}${ok ? "" : " off"}`} title={k === "face" && !ok ? t("pub.cover_no_face") : undefined}>
                      <input
                        type="radio"
                        name="pub-cover"
                        checked={on}
                        disabled={!ok}
                        onChange={() => (k === "custom" && !covers?.custom ? thumbInput.current?.click() : set({ cover: { ...meta.cover, kind: k } }))}
                      />
                      <span className="cover-img">
                        {k === "none" ? (
                          <Icon name="x" size={22} />
                        ) : k === "custom" && !covers?.custom ? (
                          <Icon name="image" size={22} />
                        ) : k === "face" && !covers ? (
                          <span className="spinner" style={{ width: 14, height: 14 }} />
                        ) : ok ? (
                          <img src={coverSrc(k)} alt="" loading="lazy" />
                        ) : (
                          <Icon name="camera" size={22} />
                        )}
                      </span>
                      <span className="cover-name">
                        {t(`pub.cover.${k}`)}
                        {k === "face" && covers?.face && <span className="muted mono"> · {num(covers.face.score)}</span>}
                      </span>
                    </label>
                  );
                })}
              </div>
              <input ref={thumbInput} type="file" hidden accept="image/jpeg,image/png" onChange={(e) => pickThumb(e.target.files?.[0])} />
              {meta.cover.kind === "face" && covers?.face && (
                <span className="field-hint">
                  {t("pub.face_found", { t: fmtTime(covers.face.at ?? 0) })} · {covers.face.reasons.map((r) => t(`pub.face_reason.${r}`)).join(", ")}
                </span>
              )}
              {meta.cover.kind === "custom" && (
                <button type="button" className="link-btn field-hint" onClick={() => thumbInput.current?.click()}>
                  {t("pub.cover_pick_again")}
                </button>
              )}
              {data.ai.cover_prompt && (
                <details className="field-hint">
                  <summary>{t("pub.cover_ai_idea")}</summary>
                  <span dir="auto">{data.ai.cover_prompt}</span>
                </details>
              )}
            </fieldset>
            {meta.cover.kind !== "none" && meta.cover.kind !== "custom" && (
              <label className="field">
                <span className="field-label">{t("pub.cover_text")}</span>
                <span className="inline-row">
                  <input className="input" dir="auto" maxLength={80} value={coverText} onChange={(e) => setCoverText(e.target.value)} />
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setCoverText(meta.title)}>
                    {t("pub.cover_use_title")}
                  </button>
                </span>
              </label>
            )}
            {meta.cover.kind !== "none" &&
              (wide ? (
                <p className="field-hint">
                  <Icon name="image" size={12} /> {t("pub.cover_wide_hint")}
                </p>
              ) : (
                <div className="toggle-row">
                  <Toggle checked={meta.cover.burn} onChange={(v) => set({ cover: { ...meta.cover, burn: v } })} label={t("pub.cover_burn")} />
                  <span>
                    {t("pub.cover_burn")}
                    <span className="field-hint" style={{ display: "block" }}>
                      {t("pub.cover_burn_hint")}
                    </span>
                  </span>
                </div>
              ))}

            <div className="export-two">
              <label className="field">
                <span className="field-label">{t("pub.preset")}</span>
                <select className="select" value={meta.preset} disabled={!!live} onChange={(e) => set({ preset: e.target.value as PublishMeta["preset"] })}>
                  {data.presets.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
                {tooLong && <span className="field-hint warn-text">{t("export.warn.too_long", { max: fmtTime(preset.max_seconds ?? 0), dur: fmtTime(data.clip.duration) })}</span>}
              </label>
              <div className="field">
                <span className="field-label">{t("pub.render")}</span>
                <div className="toggle-row">
                  <Toggle checked={meta.burn_captions} onChange={(v) => set({ burn_captions: v })} label={t("export.burn")} />
                  <span>{t("export.burn")}</span>
                </div>
                {data.ab && !wide && (
                  <div className="toggle-row">
                    <Toggle checked={meta.source === "auto"} onChange={(v) => set({ source: v ? "auto" : "export" })} label={t("pub.source_ab")} />
                    <span>
                      {t("pub.source_ab")}
                      <span className="field-hint" style={{ display: "block" }}>
                        {t("pub.source_ab_hint")}
                      </span>
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="field pub-when">
              <span className="field-label">{t("pub.when")}</span>
              <span className="inline-row">
                <input
                  className="input"
                  type="datetime-local"
                  value={whenAt}
                  min={localInput(new Date(Date.now() + 15 * 60 * 1000))}
                  aria-label={t("pub.when")}
                  onChange={(e) => setWhenAt(e.target.value)}
                />
                <button type="button" className="btn btn-sm" onClick={nextSlot} disabled={busy}>
                  <Icon name="sparkles" />
                  {t("pub.next_slot")}
                </button>
              </span>
              <span className="field-hint">
                {t("pub.when_hint", { n: limits.effective_limit, times: limits.best_times.times.join(", ") })}
                {whenAt && canSchedule && <> · {relTime(new Date(whenAt).toISOString())}</>}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ schedule many clips

export function ScheduleDialog({ rows, settings, onClose, onDone }: { rows: LibraryRow[]; settings: PublishSettings; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const when = useWhen();
  const toast = useToast();
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [preview, setPreview] = useState<ScheduleResult | null>(null);
  const [times, setTimes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const clips = rows.map((r) => ({ project_id: r.project_id, clip_id: r.clip_id }));

  useEffect(() => {
    api
      .schedule({ clips, mode: "auto", dry_run: true })
      .then((r) => {
        setPreview(r);
        setTimes(Object.fromEntries(r.planned.map((p) => [p.key, localInput(new Date(p.publish_at))])));
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const confirm = async () => {
    setBusy(true);
    try {
      const r =
        mode === "auto"
          ? await api.schedule({ clips, mode: "auto" })
          : await api.schedule({
              clips: rows.filter((x) => times[x.key]).map((x) => ({ project_id: x.project_id, clip_id: x.clip_id, publish_at: new Date(times[x.key]).toISOString() })),
              mode: "manual",
            });
      const moved = r.planned.filter((p) => p.moved).length;
      toast({ kind: "ok", text: t("pub.scheduled_n", { n: r.planned.length }) + (moved ? ` · ${t("pub.moved_n", { n: moved })}` : "") });
      if (r.skipped.length) toast({ kind: "err", text: r.skipped.map((s) => t(`pub.skip.${s.reason}`)).join(" · ") });
      onDone();
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };

  const planned = new Map((preview?.planned ?? []).map((p) => [p.key, p]));
  const skipped = new Map((preview?.skipped ?? []).map((s) => [s.key, s]));
  return (
    <Modal
      title={t("pub.schedule_n", { n: rows.length })}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="export-sum muted">{t("pub.limit_line", { n: settings.effective_limit, times: settings.best_times.times.join(", ") })}</div>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" onClick={confirm} disabled={busy || !preview || preview.planned.length === 0}>
            <Icon name="calendar" />
            {t("pub.schedule")}
          </button>
        </>
      }
    >
      <Segmented<"auto" | "manual">
        value={mode}
        options={[
          { value: "auto", label: t("pub.mode_auto") },
          { value: "manual", label: t("pub.mode_manual") },
        ]}
        onChange={setMode}
        label={t("pub.schedule")}
      />
      <p className="field-hint">
        {mode === "auto" ? t("pub.mode_auto_hint") : t("pub.mode_manual_hint")}{" "}
        {settings.best_times.source === "learned" ? t("pub.times_learned", { n: settings.best_times.samples }) : t("pub.times_default")}
      </p>
      <ol className="plan-list">
        {rows.map((r) => {
          const p = planned.get(r.key);
          const s = skipped.get(r.key);
          return (
            <li key={r.key}>
              <span className="plan-title" dir="auto">
                <b>{r.title}</b>
                <span className="muted"> · {r.project_title}</span>
              </span>
              {s ? (
                <span className="warn-text">{t(`pub.skip.${s.reason}`)}</span>
              ) : mode === "auto" ? (
                <span className="mono">{p ? when.full(p.publish_at) : "…"}</span>
              ) : (
                <input
                  className="input input-sm"
                  type="datetime-local"
                  aria-label={t("pub.when_for", { title: r.title })}
                  value={times[r.key] ?? ""}
                  min={localInput(new Date(Date.now() + 15 * 60 * 1000))}
                  onChange={(e) => setTimes({ ...times, [r.key]: e.target.value })}
                />
              )}
            </li>
          );
        })}
      </ol>
    </Modal>
  );
}

// ------------------------------------------------------------------ Settings: publishing

export function PublishingCard() {
  const { t, num } = useI18n();
  const toast = useToast();
  const [s, setS] = useState<PublishSettings | null>(null);
  const [times, setTimes] = useState("");
  useEffect(() => {
    api
      .publishSettings()
      .then((x) => {
        setS(x);
        setTimes(x.times.join(", "));
      })
      .catch(() => {});
  }, []);
  const save = (body: Parameters<typeof api.savePublishSettings>[0]) =>
    api
      .savePublishSettings(body)
      .then((x) => {
        setS(x);
        setTimes(x.times.join(", "));
        toast({ kind: "ok", text: t("common.saved") });
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  if (!s) return null;
  return (
    <section className="card setting" id="publishing">
      <div>
        <h2>{t("pub.settings_title")}</h2>
        <p>{t("pub.settings_desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 12, alignContent: "start" }}>
        <div className="toggle-row">
          <Toggle checked={s.auto} onChange={(v) => save({ auto: v })} label={t("pub.auto")} />
          <span>
            {t("pub.auto")}
            <span className="field-hint" style={{ display: "block" }}>
              {t("pub.auto_hint")}
            </span>
          </span>
        </div>
        <label className="inline-field">
          <span>{t("pub.daily_limit")}</span>
          <input
            className="input"
            type="number"
            min={1}
            max={50}
            defaultValue={s.daily_limit}
            key={s.daily_limit}
            onBlur={(e) => {
              const n = Math.max(1, Math.min(50, Number(e.target.value) || 3));
              if (n !== s.daily_limit) save({ daily_limit: n });
            }}
          />
        </label>
        {s.daily_limit > s.quota_capacity && (
          <span className="field-hint warn-text">{t("pub.limit_capped", { n: num(s.quota_capacity) })}</span>
        )}
        <label className="field">
          <span className="field-label">{t("pub.times")}</span>
          <input
            className="input mono"
            value={times}
            onChange={(e) => setTimes(e.target.value)}
            onBlur={() => {
              const list = splitList(times);
              if (list.join(",") !== s.times.join(",")) save({ times: list });
            }}
            placeholder="12:00, 18:00, 21:00"
          />
          <span className="field-hint">
            {t("pub.times_now", { times: s.best_times.times.join(", ") })}{" "}
            {s.best_times.source === "learned" ? t("pub.times_learned", { n: s.best_times.samples }) : t("pub.times_default")}
          </span>
        </label>
        <div className="toggle-row">
          <Toggle checked={s.learn_times} onChange={(v) => save({ learn_times: v })} label={t("pub.learn")} />
          <span>
            {t("pub.learn")}
            <span className="field-hint" style={{ display: "block" }}>
              {t("pub.learn_hint", { n: 10 })}
            </span>
          </span>
        </div>
        <a className="btn btn-sm" style={{ justifySelf: "start" }} href={href.publish()}>
          <Icon name="calendar" />
          {t("pub.open_library")}
        </a>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ one new time

export function RescheduleDialog({ row, onClose, onDone }: { row: LibraryRow; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const when = useWhen();
  const toast = useToast();
  const [at, setAt] = useState(row.publish_at ? localInput(new Date(row.publish_at)) : "");
  const [busy, setBusy] = useState(false);
  const ok = !!at && new Date(at).getTime() > Date.now() + 14 * 60 * 1000;
  const go = async () => {
    setBusy(true);
    try {
      const r = await api.reschedule(row.project_id, row.clip_id, new Date(at).toISOString(), false);
      toast({ kind: "ok", text: t(r.moved ? "pub.moved_to" : "pub.scheduled_for", { when: when.full(r.publish_at) }) });
      onDone();
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  return (
    <Modal
      title={t("pub.reschedule_title")}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" onClick={go} disabled={!ok || busy}>
            {t("pub.reschedule")}
          </button>
        </>
      }
    >
      <p dir="auto" style={{ marginTop: 0 }}>
        <b>{row.title}</b>
      </p>
      <input className="input" type="datetime-local" aria-label={t("pub.when")} value={at} min={localInput(new Date(Date.now() + 15 * 60 * 1000))} onChange={(e) => setAt(e.target.value)} />
      <p className="field-hint">{t("pub.reschedule_hint")}</p>
    </Modal>
  );
}
