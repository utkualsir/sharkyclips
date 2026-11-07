import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  urls,
  type Candidate,
  type ClipExport,
  type ExportEstimate,
  type ExportOptions,
  type ExportPreset,
  type FormatId,
  type Privacy,
  type PresetId,
  type RenderedClip,
  type UploadBody,
  type YoutubeStatus,
  type YoutubeUpload,
  type HookTest,
  type HookTests,
} from "../api";
import { fmtBytes, fmtTime } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { useToast } from "../toast";
import { RealTestNote } from "./HookTest";
import { AiVoiceSwitches } from "./Licenses";
import { aboutApi, type AiVoiceInfo } from "../extras";
import { LockBanner } from "./PublishTools";
import { Icon } from "./Icons";
import { Modal, Segmented, Toggle } from "./ui";
import { AdvancedWizard, ChannelPicker, ConnectPrompt, ConnectYoutube, NoChannel, VerificationStatus, YoutubeAccount } from "./YoutubeConnect";

let optionsCache: Promise<ExportOptions> | null = null;
export function exportOptions(): Promise<ExportOptions> {
  if (!optionsCache) optionsCache = api.exportOptions().catch((e) => ((optionsCache = null), Promise.reject(e)));
  return optionsCache;
}

const FORMAT_ORDER: FormatId[] = ["mp4_h264", "mp4_hevc", "mp4_av1", "mov", "webm_vp9", "gif", "mp3", "m4a"];

function presetLine(p: ExportPreset, t: ReturnType<typeof useI18n>["t"], num: (n: number) => string) {
  const parts = [`${p.width}×${p.height}`, `${num(p.fps)} fps`, `${num(Math.round(p.bitrate_k / 1000))} Mbit/s`];
  if (p.max_seconds) parts.push(t("export.max_len", { t: fmtTime(p.max_seconds) }));
  return parts.join(" · ");
}

function langName(code: string | null | undefined) {
  return UI_LANGUAGES.find((l) => l.code === code)?.name ?? code ?? "";
}

// ------------------------------------------------------------------ export dialog

export function ExportDialog({
  projectId,
  candidates,
  initial,
  spokenLang,
  onClose,
}: {
  projectId: string;
  candidates: Candidate[];
  initial: string[];
  spokenLang: string | null;
  onClose: () => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [opts, setOpts] = useState<ExportOptions | null>(null);
  const [ids, setIds] = useState<Set<string>>(() => new Set(initial));
  const [preset, setPreset] = useState<PresetId | null>(null);
  const [format, setFormat] = useState<FormatId | null>("mp4_h264");
  const [burn, setBurn] = useState(true);
  const [srt, setSrt] = useState(false);
  const [vtt, setVtt] = useState(false);
  const [subLang, setSubLang] = useState("");
  const [fcpxml, setFcpxml] = useState(false);
  const [premiere, setPremiere] = useState(false);
  const [gifMb, setGifMb] = useState(10);
  const [est, setEst] = useState<ExportEstimate | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    exportOptions()
      .then((o) => {
        setOpts(o);
        setGifMb(o.gif_default_mb);
      })
      .catch((e) => toast({ kind: "err", text: e.message }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = opts?.formats.find((f) => f.id === format) ?? null;
  const audioOnly = fmt?.kind === "audio";
  const presetObj = opts?.presets.find((p) => p.id === preset) ?? null;
  const ordered = useMemo(() => [...candidates].sort((a, b) => a.rank - b.rank), [candidates]);
  const chosen = ordered.filter((c) => ids.has(c.id));

  // Estimated size (debounced; the server knows this PC's measured sizes)
  useEffect(() => {
    if (!chosen.length) {
      setEst(null);
      return;
    }
    const id = window.setTimeout(() => {
      api
        .exportEstimate(projectId, {
          clip_ids: chosen.map((c) => c.id),
          format,
          preset: audioOnly ? null : preset,
          gif_max_mb: gifMb,
        })
        .then(setEst)
        .catch(() => setEst(null));
    }, 200);
    return () => window.clearTimeout(id);
  }, [projectId, format, preset, gifMb, audioOnly, chosen.map((c) => c.id).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickPreset = (p: PresetId | null) => {
    setPreset(p);
    if (p && (format == null || audioOnly)) setFormat("mp4_h264");
  };
  const toggleId = (cid: string) => {
    const next = new Set(ids);
    if (next.has(cid)) next.delete(cid);
    else next.add(cid);
    setIds(next);
  };
  const nothing = !format && !srt && !vtt && !fcpxml && !premiere;
  const tooLong = est?.clips.filter((c) => c.warnings.some((w) => w.code === "too_long")) ?? [];
  const needsAi = (srt || vtt || fcpxml || premiere) && subLang && subLang !== spokenLang;

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api.exportClips(projectId, {
        clip_ids: chosen.map((c) => c.id),
        format,
        preset: audioOnly ? null : preset,
        burn_captions: burn,
        subtitles: [...(srt ? (["srt"] as const) : []), ...(vtt ? (["vtt"] as const) : [])],
        subtitle_lang: subLang,
        editors: [...(fcpxml ? (["fcpxml"] as const) : []), ...(premiere ? (["premiere"] as const) : [])],
        gif_max_mb: gifMb,
      });
      toast({ kind: "ok", text: t("export.queued", { n: r.jobs.length }) });
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };

  return (
    <Modal
      title={t("export.title")}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="export-sum">
            {est && format && (
              <span>
                {t("export.estimate")}: <b className="mono">≈ {fmtBytes(est.bytes)}</b>
                <span className="muted"> · {t("export.time", { t: fmtTime(est.seconds) })}</span>
              </span>
            )}
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !chosen.length || nothing}>
            <Icon name="download" />
            {t("export.button", { n: chosen.length })}
          </button>
        </>
      }
    >
      {!opts ? (
        <div className="skeleton-lines">
          {[80, 60, 90, 40].map((w) => (
            <div key={w} className="skeleton" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : (
        <div className="export-dialog">
          <section>
            <div className="field-head">
              <span className="field-label">{t("export.clips")}</span>
              <button className="link-btn" onClick={() => setIds(new Set(ids.size === ordered.length ? [] : ordered.map((c) => c.id)))}>
                {ids.size === ordered.length ? t("export.select_none") : t("export.select_all")}
              </button>
            </div>
            <div className="export-clips">
              {ordered.map((c) => {
                const warn = est?.clips.find((x) => x.clip_id === c.id)?.warnings.some((w) => w.code === "too_long");
                return (
                  <button
                    key={c.id}
                    className={`chip-toggle${ids.has(c.id) ? " on" : ""}${warn && ids.has(c.id) ? " warn" : ""}`}
                    onClick={() => toggleId(c.id)}
                    aria-pressed={ids.has(c.id)}
                  >
                    <span className="mono">#{String(c.rank).padStart(2, "0")}</span>
                    <span className="muted">{fmtTime(c.duration)}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <section>
            <span className="field-label">{t("export.platform")}</span>
            <div className="preset-grid">
              <button className={`preset${preset == null ? " on" : ""}`} onClick={() => pickPreset(null)}>
                <b>{t("export.custom")}</b>
                <span>{t("export.custom_desc")}</span>
              </button>
              {opts.presets.map((p) => (
                <button
                  key={p.id}
                  className={`preset${preset === p.id ? " on" : ""}`}
                  onClick={() => pickPreset(p.id)}
                  disabled={audioOnly}
                >
                  <b>
                    <span className={`preset-shape ${p.frame}`} aria-hidden="true" />
                    {p.label}
                  </b>
                  <span>{presetLine(p, t, num)}</span>
                </button>
              ))}
            </div>
            {presetObj && <p className="field-hint">{t("export.safe_hint", { name: presetObj.label })}</p>}
            {tooLong.length > 0 && presetObj?.max_seconds && (
              <div className="notice notice-warn">
                <Icon name="alert" />
                <span>
                  {t("export.too_long", {
                    n: tooLong.length,
                    name: presetObj.label,
                    t: fmtTime(presetObj.max_seconds),
                  })}
                </span>
              </div>
            )}
          </section>

          <section>
            <span className="field-label">{t("export.format")}</span>
            <div className="format-grid">
              {FORMAT_ORDER.map((id) => {
                const f = opts.formats.find((x) => x.id === id);
                if (!f) return null;
                return (
                  <button
                    key={id}
                    className={`format${format === id ? " on" : ""}`}
                    onClick={() => setFormat(format === id && (srt || vtt || fcpxml || premiere) ? null : id)}
                    disabled={!f.available}
                    title={f.available ? f.encoder ?? "" : t(`export.unavailable.${id === "mp4_av1" ? "av1" : "codec"}`)}
                  >
                    <b>{f.label}</b>
                    <span>{t(`export.fmt.${id}`)}</span>
                    {f.available && f.hardware && <span className="format-hw">{t("export.gpu")}</span>}
                    {!f.available && <span className="format-hw off">{t("export.not_here")}</span>}
                  </button>
                );
              })}
            </div>
            {format === "gif" && (
              <label className="inline-field">
                <span>{t("export.gif_limit")}</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  value={gifMb}
                  onChange={(e) => setGifMb(Math.max(1, Math.min(100, Number(e.target.value) || 10)))}
                />
                <span className="muted">MB</span>
              </label>
            )}
            {!audioOnly && format && (
              <div className="toggle-row">
                <Toggle checked={burn} onChange={setBurn} label={t("export.burn")} />
                <span>{t("export.burn")}</span>
              </div>
            )}
          </section>

          <section className="export-two">
            <div>
              <span className="field-label">{t("export.sub_files")}</span>
              <div className="check-row">
                <label>
                  <input type="checkbox" checked={srt} onChange={(e) => setSrt(e.target.checked)} /> SRT
                </label>
                <label>
                  <input type="checkbox" checked={vtt} onChange={(e) => setVtt(e.target.checked)} /> VTT
                </label>
                <select className="select select-sm" value={subLang} onChange={(e) => setSubLang(e.target.value)} aria-label={t("export.sub_lang")}>
                  <option value="">{t("export.sub_spoken", { lang: langName(spokenLang) })}</option>
                  {UI_LANGUAGES.filter((l) => l.code !== spokenLang).map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>
              {needsAi && <p className="field-hint">{t("export.sub_translate")}</p>}
            </div>
            <div>
              <span className="field-label">{t("export.editors")}</span>
              <div className="check-row">
                <label title="DaVinci Resolve · Final Cut Pro">
                  <input type="checkbox" checked={fcpxml} onChange={(e) => setFcpxml(e.target.checked)} /> FCPXML
                </label>
                <label title="Adobe Premiere Pro">
                  <input type="checkbox" checked={premiere} onChange={(e) => setPremiere(e.target.checked)} /> Premiere XML
                </label>
              </div>
              <p className="field-hint">{t("export.editors_hint")}</p>
            </div>
          </section>
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ export list

function exportLabel(e: ClipExport, opts: ExportOptions | null, t: ReturnType<typeof useI18n>["t"]) {
  const p = opts?.presets.find((x) => x.id === e.preset)?.label;
  const f = opts?.formats.find((x) => x.id === e.format)?.label;
  return [p, f ?? (e.format ? e.format : t("export.files_only"))].filter(Boolean).join(" · ");
}

const ROLE_LABEL: Record<string, string> = { srt: "SRT", vtt: "VTT", fcpxml: "FCPXML", premiere: "Premiere XML" };

export function ExportsList({
  projectId,
  exports,
  onChanged,
  onUpload,
}: {
  projectId: string;
  exports: ClipExport[];
  onChanged: () => void;
  onUpload?: (cid: string, source: string) => void;
}) {
  const { t, relTime } = useI18n();
  const toast = useToast();
  const [opts, setOpts] = useState<ExportOptions | null>(null);
  useEffect(() => {
    exportOptions().then(setOpts).catch(() => {});
  }, []);
  if (!exports.length) return null;
  const remove = async (e: ClipExport) => {
    try {
      await api.deleteClipExport(projectId, e.id);
      onChanged();
    } catch (err: any) {
      toast({ kind: "err", text: err.message });
    }
  };
  return (
    <ul className="exports-list">
      {exports.map((e) => {
        const media = e.files.find((f) => f.role === "media");
        const others = e.files.filter((f) => f.role !== "media");
        const video = media && /\.(mp4|mov|webm)$/i.test(media.name);
        return (
          <li key={e.id} className="export-row">
            <div className="export-main">
              <span className="mono export-rank">#{String(e.rank).padStart(2, "0")}</span>
              <div style={{ minWidth: 0 }}>
                <div className="export-name">{exportLabel(e, opts, t)}</div>
                <div className="muted export-meta">
                  {media && <span className="mono">{fmtBytes(media.size_bytes)}</span>}
                  {e.encoder && <span>{e.encoder}</span>}
                  <span>{relTime(e.created_at)}</span>
                  {e.warnings.map((w) => (
                    <span key={w.code} className="warn-text">
                      <Icon name="alert" size={11} /> {t(`export.warn.${w.code}`)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="export-actions">
              {media && (
                <a className="btn btn-sm" href={urls.clipExportFile(projectId, media.name, true)} download>
                  <Icon name="download" />
                  {media.name.split(".").pop()?.toUpperCase()}
                </a>
              )}
              {others.map((f) => (
                <a key={f.name} className="btn btn-sm btn-ghost" href={urls.clipExportFile(projectId, f.name, true)} download title={f.name}>
                  {ROLE_LABEL[f.role] ?? f.role}
                  {f.language ? <span className="muted"> {f.language}</span> : null}
                </a>
              ))}
              {video && onUpload && (
                <button className="btn btn-sm btn-ghost" onClick={() => onUpload(e.clip_id, media!.name)} title={t("yt.upload")}>
                  <Icon name="upload" />
                  YouTube
                </button>
              )}
              <button className="btn btn-sm btn-ghost icon-btn" onClick={() => remove(e)} aria-label={t("export.delete")} title={t("export.delete")}>
                <Icon name="x" />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// ------------------------------------------------------------------ YouTube upload dialog

function localInput(d: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function UploadDialog({
  projectId,
  cand,
  clip,
  exports,
  initialSource,
  hookTest = null,
  realTest = null,
  uploads = [],
  onClose,
}: {
  projectId: string;
  cand: Candidate;
  clip: RenderedClip | null;
  exports: ClipExport[];
  initialSource?: string;
  /** the clip's A/B hook variants (1.2.5): uploading one of them is the real test */
  hookTest?: HookTest | null;
  realTest?: HookTests["real_test"] | null;
  uploads?: YoutubeUpload[];
  onClose: () => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const pub = cand.publish;
  const live = uploads.find((u) => u.video_id && !u.missing) ?? null;
  const sources = useMemo(() => {
    const out: { value: string; label: string; wide: boolean }[] = [];
    if (hookTest?.files_ok) {
      for (const label of ["A", "B"] as const) {
        const v = hookTest.variants[label];
        const tag = hookTest.upload_pick.label === label ? ` · ${t(hookTest.upload_pick.how === "bandit" ? "yt.ab_tested" : "yt.ab_predicted")}` : "";
        out.push({ value: `ab:${label}`, label: `${t("yt.source_ab", { label, style: t(`ab.style.${v.style}`) })}${tag}`, wide: false });
      }
    }
    if (clip) out.push({ value: "clip", label: t("yt.source_clip"), wide: false });
    for (const e of exports.filter((x) => x.clip_id === cand.id)) {
      const m = e.files.find((f) => f.role === "media" && /\.(mp4|mov|webm)$/i.test(f.name));
      if (m) out.push({ value: m.name, label: `${m.name} · ${fmtBytes(m.size_bytes)}`, wide: e.frame === "wide" });
    }
    return out;
  }, [clip, exports, cand.id, t, hookTest]);
  const [source, setSource] = useState(
    initialSource ?? (hookTest?.files_ok && hookTest.upload_pick.label ? `ab:${hookTest.upload_pick.label}` : sources[0]?.value ?? "clip"),
  );
  const [title, setTitle] = useState(pub.titles[0] ?? cand.text.slice(0, 90));
  const [description, setDescription] = useState(pub.description ?? "");
  const [tags, setTags] = useState((pub.tags?.length ? pub.tags : (pub.hashtags ?? []).map((h) => h.replace(/^#/, ""))).join(", "));
  const [privacy, setPrivacy] = useState<Privacy>("private");
  const [schedule, setSchedule] = useState(false);
  const [when, setWhen] = useState(() => localInput(new Date(Date.now() + 24 * 3600 * 1000)));
  const [kids, setKids] = useState(false);
  const [thumb, setThumb] = useState<"auto" | "custom" | "none">("auto");
  const [thumbV, setThumbV] = useState(0);
  const [yt, setYt] = useState<YoutubeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  // 1.2.19: a dubbed file says its voice is AI-made (both on by default)
  const [aiVoice, setAiVoice] = useState<AiVoiceInfo | null>(null);
  const [aiNote, setAiNote] = useState(true);
  const [aiSynthetic, setAiSynthetic] = useState(true);
  const thumbInput = useRef<HTMLInputElement>(null);
  const wide = sources.find((s) => s.value === source)?.wide ?? false;
  // Song credit ("Music: <song> by <channel>") of the chosen video, when it has background music.
  const credit = useMemo(() => {
    if (source === "clip") return clip?.edits?.music?.credit ?? null;
    const e = exports.find((x) => x.files.some((f) => f.name === source));
    return e?.music?.credit ?? null;
  }, [source, clip, exports]);

  useEffect(() => {
    api.youtube().then(setYt).catch(() => {});
  }, []);

  useEffect(() => {
    setAiVoice(null);
    aboutApi.aiVoice(projectId, cand.id, source).then(setAiVoice).catch(() => {});
  }, [projectId, cand.id, source]);

  // the first 3 hashtags (YouTube shows them above the title) must be in the description
  const hashtagsInDesc = useMemo(() => {
    const tagList = pub.tags?.length ? pub.hashtags ?? [] : tags.split(",").map((x) => x.trim()).filter(Boolean);
    return tagList.slice(0, 3).map((x) => `#${x.replace(/^#/, "").replace(/\s+/g, "")}`);
  }, [tags, pub.tags, pub.hashtags]);

  const pickThumb = async (file: File | undefined) => {
    if (!file) return;
    try {
      await api.uploadThumbnail(projectId, cand.id, file);
      setThumb("custom");
      setThumbV((v) => v + 1);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const submit = async () => {
    setBusy(true);
    try {
      let desc = description.trim();
      const missing = hashtagsInDesc.filter((h) => !desc.toLowerCase().includes(h.toLowerCase()));
      if (credit && !desc.includes(credit)) desc = `${desc}\n\n${credit}`.trim();
      if (missing.length) desc = `${desc}\n\n${missing.join(" ")}`.trim();
      const body: UploadBody = {
        source,
        title,
        description: desc,
        tags: tags.split(",").map((x) => x.trim()).filter(Boolean),
        privacy: schedule ? "private" : privacy,
        publish_at: schedule ? new Date(when).toISOString() : null,
        made_for_kids: kids,
        thumbnail: wide ? thumb : "none",
        language: pub.language,
        ai_voice_note: aiNote,
        synthetic_media: aiSynthetic,
      };
      if (source.startsWith("ab:") && hookTest) {
        body.ab_how = source === `ab:${hookTest.upload_pick.label}` ? hookTest.upload_pick.how ?? "manual" : "manual";
      }
      await api.uploadClip(projectId, cand.id, body);
      toast({ kind: "ok", text: t("yt.queued") });
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };

  const notConnected = yt && !yt.connected;
  const noQuota = yt && yt.quota.uploads_left < 1;
  return (
    <Modal
      title={t("yt.upload_title", { n: cand.rank })}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="export-sum">
            {yt?.connected && (
              <span className={noQuota ? "warn-text" : "muted"}>
                {t("yt.left_today", { n: yt.quota.uploads_left })}
              </span>
            )}
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !!live || !!notConnected || !!noQuota || !title.trim() || !sources.length}>
            <Icon name="upload" />
            {t("yt.upload")}
          </button>
        </>
      }
    >
      <div className="export-dialog">
        {live && (
          <div className="notice notice-warn">
            <Icon name="alert" />
            <span>
              {t("yt.already")}{" "}
              <a href={live.url} target="_blank" rel="noreferrer">
                {live.url}
              </a>
            </span>
          </div>
        )}
        {hookTest && !live && <RealTestNote realTest={realTest} />}
        {notConnected && <ConnectPrompt onConnected={setYt} />}
        {yt?.channel && (
          <p className="muted" style={{ margin: 0 }}>
            {t("yt.to_channel", { name: yt.channel.title })}
          </p>
        )}
        <label className="field">
          <span className="field-label">{t("yt.file")}</span>
          {sources.length ? (
            <select className="select" value={source} onChange={(e) => setSource(e.target.value)}>
              {sources.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          ) : (
            <span className="muted">{t("yt.no_file")}</span>
          )}
        </label>
        <label className="field">
          <span className="field-label">
            {t("yt.title_label")} <span className="muted mono">{num(title.length)}/100</span>
          </span>
          <input className="input" dir="auto" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} list="yt-titles" />
          <datalist id="yt-titles">
            {pub.titles.map((x) => (
              <option key={x} value={x} />
            ))}
          </datalist>
        </label>
        <label className="field">
          <span className="field-label">{t("yt.description")}</span>
          <textarea className="input" dir="auto" rows={5} value={description} onChange={(e) => setDescription(e.target.value)} />
          {credit && !description.includes(credit) && (
            <span className="field-hint">
              <Icon name="music" size={12} /> {t("yt.credit_added")}: <span className="mono">{credit}</span>
            </span>
          )}
        </label>
        {aiVoice?.dub && (
          <AiVoiceSwitches info={aiVoice} note={aiNote} synthetic={aiSynthetic} onNote={setAiNote} onSynthetic={setAiSynthetic} />
        )}
        <label className="field">
          <span className="field-label">{t("yt.tags")}</span>
          <input className="input" dir="auto" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="deltaforce, gaming" />
          <span className="field-hint">{t("yt.tags_hint")}</span>
        </label>
        <div className="export-two">
          <div className="field">
            <span className="field-label">{t("yt.privacy")}</span>
            <Segmented<Privacy>
              value={schedule ? "private" : privacy}
              options={(["private", "unlisted", "public"] as Privacy[]).map((p) => ({ value: p, label: t(`yt.privacy.${p}`) }))}
              onChange={(p) => {
                setPrivacy(p);
                setSchedule(false);
              }}
              label={t("yt.privacy")}
            />
            <div className="toggle-row">
              <Toggle checked={schedule} onChange={setSchedule} label={t("yt.schedule")} />
              <span>{t("yt.schedule")}</span>
            </div>
            {schedule && (
              <input className="input" type="datetime-local" value={when} min={localInput(new Date())} onChange={(e) => setWhen(e.target.value)} />
            )}
          </div>
          <div className="field">
            <span className="field-label">{t("yt.kids")}</span>
            <Segmented<"no" | "yes">
              value={kids ? "yes" : "no"}
              options={[
                { value: "no", label: t("yt.kids_no") },
                { value: "yes", label: t("yt.kids_yes") },
              ]}
              onChange={(v) => setKids(v === "yes")}
              label={t("yt.kids")}
            />
            <span className="field-hint">{t("yt.kids_hint")}</span>
          </div>
        </div>
        {wide && (
          <div className="field">
            <span className="field-label">{t("yt.thumbnail")}</span>
            <div className="thumb-row">
              {thumb !== "none" && (
                <img className="thumb-preview" src={urls.thumbnail(projectId, cand.id, thumb === "custom" ? "custom" : "auto", thumbV)} alt="" />
              )}
              <div style={{ display: "grid", gap: 8 }}>
                <Segmented<"auto" | "custom" | "none">
                  value={thumb}
                  options={[
                    { value: "auto", label: t("yt.thumb_auto") },
                    { value: "custom", label: t("yt.thumb_custom") },
                    { value: "none", label: t("yt.thumb_none") },
                  ]}
                  onChange={(v) => (v === "custom" ? thumbInput.current?.click() : setThumb(v))}
                  label={t("yt.thumbnail")}
                />
                <input ref={thumbInput} type="file" hidden accept="image/jpeg,image/png" onChange={(e) => pickThumb(e.target.files?.[0])} />
                <span className="field-hint">{t("yt.thumb_hint")}</span>
              </div>
            </div>
          </div>
        )}
        <p className="field-hint">
          <Icon name="alert" size={12} /> {t("yt.private_lock")}
        </p>
      </div>
    </Modal>
  );
}

export function UploadsLine({ uploads }: { uploads: YoutubeUpload[] }) {
  const { t, num } = useI18n();
  if (!uploads.length) return null;
  return (
    <div className="uploads-line">
      {uploads.map((u) => (
        <a key={u.video_id} href={u.url} target="_blank" rel="noreferrer" className="chip chip-outline" title={u.title}>
          <Icon name="link" size={12} />
          YouTube · {t(`yt.privacy.${u.privacy}`)}
          {u.views != null && <span className="mono"> · {num(u.views)} {t("cal.views")}</span>}
        </a>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Settings: YouTube

// The project site (docs/site, published with .github/workflows/pages.yml).
const PRIVACY_URL = "https://utkualsir.github.io/sharkyclips-site/privacy.html";

export function YoutubeCard({ isLocal, quota, onQuota }: { isLocal: boolean; quota: number; onQuota: (n: number) => void }) {
  const { t, num, relTime } = useI18n();
  const toast = useToast();
  const [yt, setYt] = useState<YoutubeStatus | null>(null);
  const [wizard, setWizard] = useState(false);
  const refresh = () => api.youtube().then(setYt).catch(() => {});

  useEffect(() => {
    refresh();
    if (window.location.hash.includes("youtube-advanced")) setWizard(true);
  }, []);

  const run = async (fn: () => Promise<YoutubeStatus | void>) => {
    try {
      const s = await fn();
      if (s) setYt(s);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  return (
    <section className="card setting" id="youtube">
      <div>
        <h2>{t("yt.settings_title")}</h2>
        <p>{t("yt.settings_desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 12, alignContent: "start", minWidth: 0 }}>
        {!yt ? (
          <div className="skeleton-lines">
            <div className="skeleton" style={{ width: "70%" }} />
            <div className="skeleton" style={{ width: "40%" }} />
          </div>
        ) : yt.connected ? (
          <>
            <YoutubeAccount
              yt={yt}
              onStatus={setYt}
              onDisconnect={isLocal ? () => run(api.youtubeDisconnect) : undefined}
              meta={
                <div className="muted" style={{ fontSize: 12 }}>
                  {t("yt.connected_since", { when: relTime(yt.connected_at ?? "") })}
                </div>
              }
            />
            {yt.no_channel && <NoChannel yt={yt} onStatus={setYt} />}
            <ChannelPicker yt={yt} onStatus={setYt} />
            <LockBanner lock={yt.lock} />
            {yt.manage === false && (
              <div className="notice notice-warn">
                <Icon name="alert" />
                <span>{t("pub.need_manage")}</span>
              </div>
            )}
            {yt.analytics === false && (
              <div className="notice">
                <Icon name="chart" />
                <span>{t("yt.no_analytics")}</span>
              </div>
            )}
            <div className="yt-quota">
              <div className="bar">
                <span style={{ width: `${Math.min(100, (yt.quota.used / yt.quota.limit) * 100)}%` }} />
              </div>
              <span className="muted">
                {t("yt.quota_line", {
                  n: yt.quota.uploads_left,
                  used: num(yt.quota.used),
                  limit: num(yt.quota.limit),
                })}
              </span>
            </div>
            {yt.token_protection && (
              <span className="muted" style={{ fontSize: 12 }}>
                <Icon name="lock" size={12} /> {t(`yt.token_${yt.token_protection}`)}
              </span>
            )}
            {yt.last_synced && (
              <span className="muted" style={{ fontSize: 12 }}>
                {t("yt.synced", { when: relTime(new Date(yt.last_synced * 1000).toISOString()) })}
              </span>
            )}
          </>
        ) : (
          <>
            {yt.signed_out && (
              <div className="notice notice-warn">
                <Icon name="alert" />
                <span>
                  {yt.signed_out.channel
                    ? t("ytc.signed_out_banner", { name: yt.signed_out.channel.title })
                    : t("ytc.signed_out_banner_plain")}
                </span>
              </div>
            )}
            <ConnectYoutube
              yt={yt}
              onStatus={setYt}
              label={yt.signed_out ? t("ytc.reconnect") : undefined}
              onAdvanced={() => setWizard(true)}
            />
          </>
        )}
        {yt && <VerificationStatus yt={yt} />}
        {yt?.mode === "own" && (
          <div className="sugg">
            <Icon name="check" />
            <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
              {t("ytc.mode_own", { project: yt.project_id ?? yt.client_id ?? "" })}
            </span>
            {isLocal && yt.shared.available && (
              <button className="btn btn-sm btn-ghost" onClick={() => run(api.youtubeRemoveClient)}>
                {t("ytc.back_to_easy")}
              </button>
            )}
            {isLocal && !yt.shared.available && (
              <button className="btn btn-sm btn-ghost" onClick={() => run(api.youtubeRemoveClient)}>
                {t("yt.remove_client")}
              </button>
            )}
          </div>
        )}
        <div className="yt-legal muted">
          <p>{t("yt.legal")}</p>
          <p>
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">{t("yt.legal_tos")}</a>
            {" · "}
            <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">{t("yt.legal_google")}</a>
            {" · "}
            <a href={PRIVACY_URL} target="_blank" rel="noreferrer">{t("yt.legal_privacy")}</a>
            {" · "}
            <a href="https://myaccount.google.com/permissions" target="_blank" rel="noreferrer">{t("yt.legal_manage")}</a>
          </p>
        </div>
        {yt && isLocal && (
          <details className="ytc-adv" open={wizard} onToggle={(e) => setWizard((e.target as HTMLDetailsElement).open)}>
            <summary>{t("ytc.adv_title")}</summary>
            <p className="muted ytc-sub">{t("ytc.adv_why")}</p>
            {wizard && <AdvancedWizard yt={yt} onStatus={setYt} onClose={() => setWizard(false)} initialStep={yt.mode === "own" ? 4 : 0} />}
          </details>
        )}
        <label className="inline-field">
          <span>{t("yt.quota_setting")}</span>
          <input
            className="input"
            type="number"
            min={100}
            step={100}
            defaultValue={quota}
            onBlur={(e) => {
              const n = Math.max(100, Number(e.target.value) || 10000);
              if (n !== quota) onQuota(n);
            }}
          />
        </label>
      </div>
    </section>
  );
}
