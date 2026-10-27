import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  urls,
  type BrandPreset,
  type BrandState,
  type LogoPos,
  type Mood,
  type MusicLibrary,
  type MusicTrack,
  type WordLists,
} from "../api";
import { Icon } from "../components/Icons";
import { JobLine, Segmented, Toggle } from "../components/ui";
import { fmtBytes, fmtTime } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useMeta } from "../meta";
import { href, type StudioTab } from "../router";
import { useToast } from "../toast";

const MOODS: Mood[] = ["hype", "chill", "sad", "funny"];
const POSITIONS: LogoPos[] = ["tl", "tr", "bl", "br"];
const FONTS = ["Arial", "Impact", "Montserrat", "Bebas Neue", "Segoe UI", "Verdana", "Trebuchet MS", "Comic Sans MS"];

function lines(text: string): string[] {
  const out: string[] = [];
  for (const raw of text.split(/\n/)) {
    const w = raw.trim().replace(/\s+/g, " ");
    if (w && !out.includes(w)) out.push(w);
  }
  return out;
}

// ------------------------------------------------------------------ music

function TrackRow({ track, playing, onPlay, onChanged }: { track: MusicTrack; playing: boolean; onPlay: () => void; onChanged: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [title, setTitle] = useState(track.title);
  const [artist, setArtist] = useState(track.artist);
  useEffect(() => {
    setTitle(track.title);
    setArtist(track.artist);
  }, [track.title, track.artist]);
  const save = async (body: Parameters<typeof api.updateTrack>[1]) => {
    try {
      await api.updateTrack(track.name, body);
      onChanged();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const moods = track.moods.length ? track.moods : track.mood_guess ? [track.mood_guess] : [];
  return (
    <div className="track" data-track={track.name}>
      <button className="btn btn-sm icon-btn" onClick={onPlay} aria-label={playing ? t("player.stop") : t("music.listen")} title={t("music.listen_hint")}>
        <Icon name={playing ? "pause" : "play"} />
      </button>
      <div className="track-main">
        <div className="track-names">
          <input
            className="input input-plain"
            value={title}
            maxLength={80}
            dir="auto"
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => title.trim() !== track.title && save({ title })}
            aria-label={t("music.title")}
          />
          <input
            className="input input-plain muted"
            value={artist}
            maxLength={60}
            dir="auto"
            placeholder={t("music.artist_placeholder")}
            onChange={(e) => setArtist(e.target.value)}
            onBlur={() => artist.trim() !== track.artist && save({ artist })}
            aria-label={t("music.artist")}
          />
        </div>
        <div className="track-meta">
          {track.analyzed ? (
            <>
              <span className="tc">{fmtTime(track.duration ?? 0)}</span>
              {track.bpm != null && <span className="tc">{num(track.bpm)} BPM</span>}
              {track.best_start != null && <span>{t("music.strong_part", { t: fmtTime(track.best_start) })}</span>}
            </>
          ) : (
            <span className="muted">{t("music.not_analyzed")}</span>
          )}
          <span className="muted">{fmtBytes(track.size_bytes)}</span>
        </div>
      </div>
      <div className="mood-chips" role="group" aria-label={t("music.moods")}>
        {MOODS.map((m) => {
          const on = moods.includes(m);
          return (
            <button
              key={m}
              type="button"
              className={`mood mood-${m}`}
              aria-pressed={on}
              onClick={() => save({ moods: on ? moods.filter((x) => x !== m) : [...moods, m] })}
            >
              {t(`mood.${m}`)}
            </button>
          );
        })}
      </div>
      <button
        className="btn btn-sm btn-ghost icon-btn danger-text"
        aria-label={t("music.delete")}
        title={t("music.delete")}
        onClick={async () => {
          if (!window.confirm(t("music.delete_confirm", { name: track.title }))) return;
          await api.deleteTrack(track.name).catch(() => {});
          onChanged();
        }}
      >
        <Icon name="trash" />
      </button>
    </div>
  );
}

function MusicTab() {
  const { t } = useI18n();
  const meta = useMeta();
  const toast = useToast();
  const { jobs, finishedTick, lastFinished } = useJobs();
  const [lib, setLib] = useState<MusicLibrary | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [uploading, setUploading] = useState(0);
  const [over, setOver] = useState(false);
  const [tpl, setTpl] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const load = () => api.music().then((l) => (setLib(l), setTpl(l.credit_template))).catch(() => {});
  useEffect(() => {
    load();
    return () => audio.current?.pause();
  }, []);
  useEffect(() => {
    if (lastFinished?.kind === "music") load();
  }, [finishedTick]); // eslint-disable-line react-hooks/exhaustive-deps
  const job = jobs.find((j) => j.kind === "music" && isActive(j));
  const pending = lib?.tracks.filter((x) => !x.analyzed).length ?? 0;

  const play = (tr: MusicTrack) => {
    if (playing === tr.name) {
      audio.current?.pause();
      setPlaying(null);
      return;
    }
    audio.current?.pause();
    const a = new Audio(urls.musicAudio(tr.name));
    a.currentTime = tr.best_start ?? 0;
    a.play().catch(() => {});
    a.onended = () => setPlaying(null);
    audio.current = a;
    setPlaying(tr.name);
  };

  const upload = async (files: FileList | File[]) => {
    const list = [...files].filter((f) => /\.(mp3|wav|m4a|aac|ogg|opus|flac)$/i.test(f.name));
    if (!list.length) {
      toast({ kind: "err", text: t("music.bad_file") });
      return;
    }
    setUploading(list.length);
    for (const f of list) {
      try {
        await api.uploadTrack(f);
      } catch (e: any) {
        toast({ kind: "err", text: `${f.name}: ${e.message}`, hint: e.hint });
      }
      setUploading((n) => n - 1);
    }
    load();
  };

  const sample = lib?.tracks.find((x) => x.analyzed) ?? lib?.tracks[0];
  const credit = (tpl || "Music: {title} by {artist}")
    .replace("{title}", sample?.title ?? t("music.sample_title"))
    .replace("{artist}", sample?.artist || t("music.sample_artist"));

  return (
    <div className="settings-list">
      <section
        className={`card setting studio-drop${over ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          upload(e.dataTransfer.files);
        }}
      >
        <div>
          <h2>{t("music.title_lib")}</h2>
          <p>{t("music.desc")}</p>
          {lib && (
            <p className="mono studio-folder" dir="ltr" title={lib.folder}>
              {lib.folder}
            </p>
          )}
        </div>
        <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
          <div className="edit-line" style={{ flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-sm" onClick={() => input.current?.click()} disabled={uploading > 0}>
              <Icon name="upload" />
              {uploading > 0 ? t("music.uploading", { n: uploading }) : t("music.add")}
            </button>
            {meta?.is_local && (
              <button className="btn btn-sm" onClick={() => api.openMusicFolder().catch((e) => toast({ kind: "err", text: e.message }))}>
                <Icon name="file" />
                {t("music.open_folder")}
              </button>
            )}
            <button className="btn btn-sm btn-ghost" onClick={load} title={t("music.rescan_hint")}>
              <Icon name="refresh" />
              {t("music.rescan")}
            </button>
          </div>
          <input
            ref={input}
            type="file"
            hidden
            multiple
            accept=".mp3,.wav,.m4a,.aac,.ogg,.opus,.flac,audio/*"
            onChange={(e) => {
              if (e.target.files) upload(e.target.files);
              e.target.value = "";
            }}
          />
          <div className="field-hint">{t("music.drop_hint")}</div>
          {job ? (
            <JobLine job={job} />
          ) : (
            pending > 0 && (
              <button className="btn btn-sm btn-gold" onClick={() => api.analyzeMusic().catch((e) => toast({ kind: "err", text: e.message }))}>
                <Icon name="sparkles" />
                {t("music.analyze", { n: pending })}
              </button>
            )
          )}
        </div>
      </section>

      <section className="card studio-tracks">
        {!lib ? (
          <div className="skeleton" style={{ height: 120 }} />
        ) : lib.tracks.length === 0 ? (
          <div className="empty" style={{ margin: 16 }}>
            <Icon name="music" size={26} />
            <p style={{ margin: 0, maxWidth: "52ch" }}>{t("music.empty")}</p>
          </div>
        ) : (
          lib.tracks.map((tr) => (
            <TrackRow key={tr.name} track={tr} playing={playing === tr.name} onPlay={() => play(tr)} onChanged={load} />
          ))
        )}
      </section>

      {lib && (
        <section className="card setting">
          <div>
            <h2>{t("music.credit")}</h2>
            <p>{t("music.credit_desc")}</p>
          </div>
          <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
            <div className="toggle-line">
              <Toggle
                checked={lib.credit_enabled}
                onChange={(v) => api.musicSettings({ credit_enabled: v }).then(setLib)}
                label={t("music.credit_on")}
              />
              <span>{t("music.credit_on")}</span>
            </div>
            <input
              className="input"
              value={tpl}
              dir="auto"
              onChange={(e) => setTpl(e.target.value)}
              onBlur={() => tpl !== lib.credit_template && api.musicSettings({ credit_template: tpl }).then(setLib)}
              placeholder="Music: {title} by {artist}"
              aria-label={t("music.credit_template")}
            />
            <div className="field-hint">
              {t("music.credit_preview")}: <span className="mono">{credit}</span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ brand kit

function BrandMock({ p }: { p: BrandPreset }) {
  const right = p.logo_pos.endsWith("r");
  const top = p.logo_pos.startsWith("t");
  const font = p.caption_font ? `"${p.caption_font}", Geist, Arial, sans-serif` : undefined;
  return (
    <div className="brand-mock" aria-hidden="true">
      <div className="brand-mock-corner" style={{ [right ? "right" : "left"]: 8, [top ? "top" : "bottom"]: 8, alignItems: right ? "flex-end" : "flex-start", flexDirection: top ? "column" : "column-reverse" }}>
        {p.logo ? (
          <img src={urls.brandLogo(p.id, p.rev)} alt="" style={{ width: `${p.logo_size * 1.6}px`, opacity: p.logo_opacity }} />
        ) : (
          <span className="brand-mock-logo" style={{ width: `${p.logo_size * 1.6}px`, opacity: p.logo_opacity }} />
        )}
        {p.show_handle && p.handle && <span className="brand-mock-handle">@{p.handle}</span>}
      </div>
      <div className="brand-mock-cap" style={{ fontFamily: font, color: p.caption_color, WebkitTextStroke: `1px ${p.caption_outline}` }}>
        THIS IS <span style={{ color: p.caption_highlight }}>HOW</span> IT LOOKS
      </div>
    </div>
  );
}

function BrandTab() {
  const { t } = useI18n();
  const toast = useToast();
  const [state, setState] = useState<BrandState | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [draft, setDraft] = useState<BrandPreset | null>(null);
  const logoInput = useRef<HTMLInputElement>(null);
  const apply = (s: BrandState, pick?: string | null) => {
    setState(s);
    const id = pick ?? sel ?? s.active ?? s.presets[0]?.id ?? null;
    const p = s.presets.find((x) => x.id === id) ?? s.presets[0] ?? null;
    setSel(p?.id ?? null);
    setDraft(p ? structuredClone(p) : null);
  };
  useEffect(() => {
    api.brand().then((s) => apply(s)).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const saved = state?.presets.find((x) => x.id === sel) ?? null;
  const dirty = !!(draft && saved && JSON.stringify(draft) !== JSON.stringify(saved));

  const save = async (presets: Partial<BrandPreset>[], active: string | null, pick?: string | null) => {
    try {
      const s = await api.saveBrand(presets, active);
      apply(s, pick);
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const add = () => {
    const presets = [...(state?.presets ?? []), { name: t("brand.new_name") }];
    api.saveBrand(presets, state?.active ?? null).then((s) => apply(s, s.presets[s.presets.length - 1]?.id));
  };
  const set = (patch: Partial<BrandPreset>) => draft && setDraft({ ...draft, ...patch });

  if (!state) return <div className="card skeleton" style={{ height: 300 }} />;
  if (!draft)
    return (
      <div className="empty">
        <Icon name="image" size={26} />
        <p style={{ margin: 0, maxWidth: "50ch" }}>{t("brand.empty")}</p>
        <button className="btn btn-primary" onClick={add}>
          <Icon name="plus" />
          {t("brand.add")}
        </button>
      </div>
    );

  return (
    <div className="settings-list">
      <div className="lang-tabs brand-presets">
        {state.presets.map((p) => (
          <button key={p.id} type="button" aria-pressed={p.id === sel} onClick={() => apply(state, p.id)}>
            {p.id === state.active && <Icon name="check" size={12} />}
            {p.name}
          </button>
        ))}
        <button className="btn btn-sm btn-ghost" onClick={add}>
          <Icon name="plus" />
          {t("brand.add")}
        </button>
      </div>
      <section className="card brand-editor">
        <div className="brand-form">
          <div className="brand-grid">
            <label>
              <span className="field-label">{t("brand.name")}</span>
              <input className="input" value={draft.name} maxLength={40} onChange={(e) => set({ name: e.target.value })} />
            </label>
            <label>
              <span className="field-label">{t("brand.channel")}</span>
              <input className="input" value={draft.channel} maxLength={60} dir="auto" onChange={(e) => set({ channel: e.target.value })} />
            </label>
            <label>
              <span className="field-label">{t("brand.handle")}</span>
              <input className="input" value={draft.handle} maxLength={40} placeholder="yourchannel" onChange={(e) => set({ handle: e.target.value })} />
            </label>
          </div>
          <div>
            <span className="field-label">{t("brand.logo")}</span>
            <div className="edit-line" style={{ marginTop: 6, flexWrap: "wrap" }}>
              {draft.logo && <img className="brand-logo-thumb" src={urls.brandLogo(draft.id, draft.rev)} alt="" />}
              <button className="btn btn-sm" onClick={() => logoInput.current?.click()}>
                <Icon name="upload" />
                {draft.logo ? t("brand.logo_replace") : t("brand.logo_add")}
              </button>
              {draft.logo && (
                <button className="btn btn-sm btn-ghost" onClick={() => api.removeLogo(draft.id).then((s) => apply(s, draft.id))}>
                  {t("brand.logo_remove")}
                </button>
              )}
              <input
                ref={logoInput}
                type="file"
                hidden
                accept=".png,.jpg,.jpeg,.webp,image/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (f) api.uploadLogo(draft.id, f).then((s) => apply(s, draft.id)).catch((er) => toast({ kind: "err", text: er.message, hint: er.hint }));
                }}
              />
            </div>
            <div className="field-hint">{t("brand.logo_hint")}</div>
          </div>
          <div className="brand-field">
            <span className="field-label">{t("brand.position")}</span>
            <Segmented<LogoPos> value={draft.logo_pos} options={POSITIONS.map((p) => ({ value: p, label: t(`brand.pos.${p}`) }))} onChange={(v) => set({ logo_pos: v })} />
          </div>
          <div className="brand-grid">
            <label>
              <span className="field-label">
                {t("brand.size")} · {Math.round(draft.logo_size)}%
              </span>
              <input type="range" min={5} max={45} value={draft.logo_size} onChange={(e) => set({ logo_size: Number(e.target.value) })} />
            </label>
            <label>
              <span className="field-label">
                {t("brand.opacity")} · {Math.round(draft.logo_opacity * 100)}%
              </span>
              <input type="range" min={10} max={100} value={Math.round(draft.logo_opacity * 100)} onChange={(e) => set({ logo_opacity: Number(e.target.value) / 100 })} />
            </label>
          </div>
          <div className="toggle-line">
            <Toggle checked={draft.show_handle} onChange={(v) => set({ show_handle: v })} label={t("brand.show_handle")} />
            <span>{t("brand.show_handle")}</span>
          </div>
          {(["intro", "outro"] as const).map((k) => (
            <div className="brand-card-row" key={k}>
              <div className="toggle-line">
                <Toggle checked={draft[k].enabled} onChange={(v) => set({ [k]: { ...draft[k], enabled: v } })} label={t(`brand.${k}`)} />
                <span>{t(`brand.${k}`)}</span>
              </div>
              {draft[k].enabled && (
                <div className="brand-card-fields">
                  <input
                    className="input"
                    value={draft[k].text}
                    maxLength={80}
                    dir="auto"
                    placeholder={k === "intro" ? draft.channel || t("brand.intro_placeholder") : draft.handle ? `@${draft.handle}` : t("brand.outro_placeholder")}
                    onChange={(e) => set({ [k]: { ...draft[k], text: e.target.value } })}
                    aria-label={t(`brand.${k}_text`)}
                  />
                  <label className="edit-line">
                    <input
                      className="input"
                      type="number"
                      min={0.5}
                      max={6}
                      step={0.5}
                      style={{ width: 80 }}
                      value={draft[k].seconds}
                      onChange={(e) => set({ [k]: { ...draft[k], seconds: Number(e.target.value) } })}
                    />
                    <span className="muted">s</span>
                  </label>
                </div>
              )}
            </div>
          ))}
          <div className="brand-grid">
            <label>
              <span className="field-label">{t("brand.font")}</span>
              <input className="input" list="brand-fonts" value={draft.caption_font} placeholder={t("brand.font_default")} onChange={(e) => set({ caption_font: e.target.value })} />
              <datalist id="brand-fonts">
                {FONTS.map((f) => (
                  <option key={f} value={f} />
                ))}
              </datalist>
            </label>
            {(["caption_color", "caption_highlight", "caption_outline", "card_color"] as const).map((k) => (
              <label key={k} className="color-field">
                <span className="field-label">{t(`brand.${k}`)}</span>
                <input type="color" value={draft[k]} onChange={(e) => set({ [k]: e.target.value.toUpperCase() })} />
              </label>
            ))}
          </div>
          <div className="save-line">
            <div className="edit-line">
              {state.active !== draft.id ? (
                <button className="btn btn-sm" onClick={() => save(state.presets, draft.id, draft.id)}>
                  {t("brand.use")}
                </button>
              ) : (
                <span className="chip chip-success">{t("brand.in_use")}</span>
              )}
              <button
                className="btn btn-sm btn-ghost danger-text"
                onClick={() => window.confirm(t("brand.delete_confirm", { name: draft.name })) && save(state.presets.filter((x) => x.id !== draft.id), state.active, null)}
              >
                {t("brand.delete")}
              </button>
            </div>
            <button className="btn btn-primary btn-sm" disabled={!dirty} onClick={() => save(state.presets.map((x) => (x.id === draft.id ? draft : x)), state.active, draft.id)}>
              {t("common.save")}
            </button>
          </div>
        </div>
        <div className="brand-side">
          <BrandMock p={draft} />
          <p className="field-hint">{t("brand.mock_hint")}</p>
        </div>
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ word lists

function WordsTab() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [data, setData] = useState<WordLists | null>(null);
  const [code, setCode] = useState(lang);
  const [swear, setSwear] = useState("");
  const [sure, setSure] = useState("");
  const [maybe, setMaybe] = useState("");
  const [ms, setMs] = useState({ light: 800, strong: 450 });
  const fill = (d: WordLists, c: string) => {
    setSwear(d.profanity[c]?.words.join("\n") ?? "");
    setSure(d.fillers[c]?.sure.join("\n") ?? "");
    setMaybe(d.fillers[c]?.maybe.join("\n") ?? "");
    setMs(d.silence_ms);
  };
  useEffect(() => {
    api.wordLists().then((d) => (setData(d), fill(d, code))).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = useMemo(() => {
    if (!data) return false;
    return (
      lines(swear).join("\n") !== data.profanity[code]?.words.join("\n") ||
      lines(sure).join("\n") !== data.fillers[code]?.sure.join("\n") ||
      lines(maybe).join("\n") !== data.fillers[code]?.maybe.join("\n") ||
      ms.light !== data.silence_ms.light ||
      ms.strong !== data.silence_ms.strong
    );
  }, [data, code, swear, sure, maybe, ms]);
  const save = async (body: Parameters<typeof api.saveWordLists>[0]) => {
    try {
      const d = await api.saveWordLists(body);
      setData(d);
      fill(d, code);
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  if (!data) return <div className="card skeleton" style={{ height: 300 }} />;
  const rtl = code === "ar" ? "rtl" : "auto";
  return (
    <div className="settings-list">
      <div className="lang-tabs" role="group">
        {UI_LANGUAGES.map((l) => (
          <button
            key={l.code}
            type="button"
            aria-pressed={code === l.code}
            onClick={() => {
              setCode(l.code);
              fill(data, l.code);
            }}
          >
            {l.name}
            {(data.profanity[l.code]?.custom || data.fillers[l.code]?.custom) && <span className="n">•</span>}
          </button>
        ))}
      </div>
      <section className="card setting">
        <div>
          <h2>{t("words.swear")}</h2>
          <p>{t("words.swear_desc")}</p>
          <p className="field-hint" style={{ marginTop: 8 }}>
            {t("words.syntax")}
          </p>
        </div>
        <div>
          <textarea className="textarea words-area" aria-label={t("words.swear")} dir={rtl} lang={code} value={swear} onChange={(e) => setSwear(e.target.value)} />
          <div className="save-line">
            <span className="muted">{t("words.count", { n: lines(swear).length })}</span>
            {data.profanity[code]?.custom && (
              <button className="btn btn-sm btn-ghost" onClick={() => save({ profanity: { [code]: null } })}>
                {t("words.reset")}
              </button>
            )}
          </div>
        </div>
      </section>
      <section className="card setting">
        <div>
          <h2>{t("words.fillers")}</h2>
          <p>{t("words.fillers_desc")}</p>
        </div>
        <div style={{ display: "grid", gap: 12 }}>
          <label>
            <span className="field-label">{t("words.fillers_sure")}</span>
            <textarea className="textarea words-area short" dir={rtl} lang={code} value={sure} onChange={(e) => setSure(e.target.value)} />
          </label>
          <label>
            <span className="field-label">{t("words.fillers_maybe")}</span>
            <textarea className="textarea words-area short" dir={rtl} lang={code} value={maybe} onChange={(e) => setMaybe(e.target.value)} />
          </label>
          {data.fillers[code]?.custom && (
            <button className="btn btn-sm btn-ghost" style={{ justifySelf: "start" }} onClick={() => save({ fillers: { [code]: null } })}>
              {t("words.reset")}
            </button>
          )}
        </div>
      </section>
      <section className="card setting">
        <div>
          <h2>{t("words.silence")}</h2>
          <p>{t("words.silence_desc")}</p>
        </div>
        <div className="brand-grid">
          {(["light", "strong"] as const).map((k) => (
            <label key={k}>
              <span className="field-label">{t(`edit.cuts.${k}`)}</span>
              <span className="edit-line">
                <input
                  className="input"
                  type="number"
                  min={150}
                  max={5000}
                  step={50}
                  value={ms[k]}
                  onChange={(e) => setMs({ ...ms, [k]: Number(e.target.value) })}
                />
                <span className="muted">ms</span>
              </span>
            </label>
          ))}
        </div>
      </section>
      <div className="save-line">
        <span className="muted">{t("words.applies")}</span>
        <button
          className="btn btn-primary"
          disabled={!dirty}
          onClick={() =>
            save({
              profanity: lines(swear).join("\n") !== data.profanity[code]?.words.join("\n") ? { [code]: lines(swear) } : undefined,
              fillers:
                lines(sure).join("\n") !== data.fillers[code]?.sure.join("\n") || lines(maybe).join("\n") !== data.fillers[code]?.maybe.join("\n")
                  ? { [code]: { sure: lines(sure), maybe: lines(maybe) } }
                  : undefined,
              silence_ms: ms,
            })
          }
        >
          {t("common.save")}
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ page

export default function Studio({ tab }: { tab: StudioTab }) {
  const { t } = useI18n();
  const tabs: StudioTab[] = ["music", "brand", "words"];
  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1 className="display">{t("studio.title")}</h1>
          <p className="lede">{t("studio.lede")}</p>
        </div>
      </div>
      <div className="side-tabs studio-tabs" role="tablist">
        {tabs.map((x) => (
          <a key={x} role="tab" aria-selected={tab === x} href={href.studio(x)}>
            <Icon name={x === "music" ? "music" : x === "brand" ? "image" : "list"} size={14} />
            {t(`studio.tab.${x}`)}
          </a>
        ))}
      </div>
      {tab === "music" && <MusicTab />}
      {tab === "brand" && <BrandTab />}
      {tab === "words" && <WordsTab />}
    </main>
  );
}
