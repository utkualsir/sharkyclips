import { useCallback, useEffect, useId, useState } from "react";
import {
  ApiError,
  channelsApi,
  type ChannelInfo,
  type ChannelLine,
  type ChannelPlatform,
  type ChannelsView,
  type ChannelVod,
  type Mode,
} from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { href } from "../router";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Segmented, Toggle } from "./ui";

/** 1.2.57 channel monitoring: Settings > Channels (Pro + Easy) and the Easy home card. */

const PLATFORM_NAME: Record<ChannelPlatform, string> = { kick: "Kick", twitch: "Twitch", youtube: "YouTube" };
const KEEP = [0, 1, 3, 7, 14, 30, -1];
const MODES: ("auto" | Mode)[] = ["auto", "gaming", "study", "music"];

function guessPlatform(text: string): ChannelPlatform | null {
  const s = text.toLowerCase();
  if (s.includes("kick.com")) return "kick";
  if (s.includes("twitch.tv")) return "twitch";
  if (s.includes("youtube.com") || s.includes("youtu.be")) return "youtube";
  return null;
}

export function useChannels(poll = 0) {
  const [view, setView] = useState<ChannelsView | null>(null);
  const toast = useToast();
  const reload = useCallback(() => channelsApi.get().then(setView).catch(() => {}), []);
  useEffect(() => {
    reload();
    if (!poll) return;
    const id = window.setInterval(reload, poll);
    return () => window.clearInterval(id);
  }, [reload, poll]);
  const run = useCallback(
    async (fn: () => Promise<ChannelsView>, ok?: string): Promise<boolean> => {
      try {
        setView(await fn());
        if (ok) toast({ kind: "ok", text: ok });
        return true;
      } catch (e) {
        if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
        return false;
      }
    },
    [toast],
  );
  return { view, reload, run, setView };
}

function fmtWhen(at: number | null | undefined, lang: string): string {
  if (!at) return "";
  try {
    return new Date(at * 1000).toLocaleString(lang, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return new Date(at * 1000).toLocaleString();
  }
}

function Avatar({ c }: { c: Pick<ChannelInfo, "avatar" | "name" | "handle" | "platform"> }) {
  const [broken, setBroken] = useState(false);
  if (c.avatar && !broken)
    return <img className="acc-avatar" src={c.avatar} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)} />;
  return (
    <span className={`acc-avatar acc-avatar-ph chan-ph-${c.platform}`} aria-hidden="true">
      {(c.name || c.handle || "?").slice(0, 1).toUpperCase()}
    </span>
  );
}

// =========================================================================== add form

function AddChannel({ onAdded, easy, run }: { onAdded?: () => void; easy?: boolean; run: ReturnType<typeof useChannels>["run"] }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [platform, setPlatform] = useState<ChannelPlatform>("kick");
  const [own, setOwn] = useState(true);
  const [busy, setBusy] = useState(false);
  const fid = useId();
  const guessed = guessPlatform(text);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    const ok = await run(() => channelsApi.add({ text: text.trim(), platform: guessed ?? platform, own }), t("chan.added"));
    setBusy(false);
    if (ok) {
      setText("");
      onAdded?.();
    }
  };
  return (
    <form className="chan-add" onSubmit={submit}>
      {!guessed && (
        <Segmented
          value={platform}
          onChange={setPlatform}
          label={t("chan.platform")}
          options={(["kick", "twitch", "youtube"] as ChannelPlatform[]).map((p) => ({ value: p, label: PLATFORM_NAME[p] }))}
        />
      )}
      <label className="field" htmlFor={fid}>
        <span className="field-label">{t("chan.add_label")}</span>
        <div className="chan-add-row">
          <input
            id={fid}
            className="input"
            dir="ltr"
            value={text}
            placeholder={t("chan.add_placeholder")}
            onChange={(e) => setText(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className="btn btn-primary" disabled={!text.trim() || busy}>
            {busy ? <span className="spinner" style={{ borderTopColor: "currentColor" }} /> : <Icon name="plus" />}
            {t("chan.add")}
          </button>
        </div>
      </label>
      {!easy && (
        <label className="chan-own">
          <input type="checkbox" checked={own} onChange={(e) => setOwn(e.target.checked)} />
          <span>{t("chan.own_label")}</span>
        </label>
      )}
      {!own && <OtherNote />}
    </form>
  );
}

function OtherNote() {
  const { t } = useI18n();
  return (
    <p className="notice notice-warn chan-note">
      <Icon name="alert" />
      <span>{t("chan.permission_note")}</span>
    </p>
  );
}

// =========================================================================== status helpers

function statusLine(c: ChannelInfo, view: ChannelsView, t: ReturnType<typeof useI18n>["t"], lang: string): string {
  if (!c.enabled) return t("chan.paused");
  if (c.fails && c.last_error) return t("chan.check_failed", { when: fmtWhen(c.next_check, lang) });
  if (c.live) return t("chan.live_now");
  const w = view.service.waiting;
  if (w && view.vods.some((v) => v.key === w.key && v.channel === c.id)) return t(`chan.wait_${w.reason}`);
  if (c.counts.downloading) return t("chan.downloading");
  if (c.counts.clipping) return t("chan.clipping");
  if (c.last_check) return t("chan.checked", { when: fmtWhen(c.last_check, lang) });
  return t("chan.first_check");
}

const CHIP: Partial<Record<ChannelVod["status"], string>> = {
  done: "chip-success", error: "chip-danger", gone: "chip-outline", skipped: "chip-outline", live: "chip-danger",
  downloading: "chip-gold", clipping: "chip-gold",
};

function VodRow({ v, run, showChannel }: { v: ChannelVod; run: ReturnType<typeof useChannels>["run"]; showChannel: boolean }) {
  const { t, lang } = useI18n();
  const canRetry = ["error", "gone", "skipped", "retry", "waiting_disk", "waiting_metered", "waiting_game"].includes(v.status) && !!v.url;
  const canSkip = ["queued", "retry", "waiting_disk", "waiting_metered", "waiting_game", "live", "processing", "upcoming"].includes(v.status);
  return (
    <li className="chan-vod">
      <div className="chan-vod-main">
        <b dir="auto" className="chan-vod-title">{v.title || v.vod_id}</b>
        <span className="muted chan-vod-meta">
          {showChannel && v.channel_name ? <span dir="auto">{v.channel_name}</span> : null}
          {v.started_at ? <span>{fmtWhen(v.started_at, lang)}</span> : null}
          {v.duration ? <span className="mono">{fmtTime(v.duration)}</span> : null}
          {v.note ? <span>{t(`chan.note_${v.note}`)}</span> : null}
        </span>
      </div>
      <div className="chan-vod-side">
        <span className={`chip ${CHIP[v.status] ?? "chip-outline"}`}>
          {v.status === "done" && v.clips != null ? t("chan.vod_done_n", { n: v.clips }) : t(`chan.vod_${v.status}`)}
        </span>
        {v.project_id && (
          <a className="btn btn-sm btn-ghost" href={href.project(v.project_id)}>
            {t("chan.open")}
          </a>
        )}
        {canRetry && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => run(() => channelsApi.retry(v.key))}>
            {t("chan.retry")}
          </button>
        )}
        {canSkip && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => run(() => channelsApi.skip(v.key))}>
            {t("chan.skip")}
          </button>
        )}
      </div>
    </li>
  );
}

// =========================================================================== one channel

function ChannelItem({ c, view, run }: { c: ChannelInfo; view: ChannelsView; run: ReturnType<typeof useChannels>["run"] }) {
  const { t, lang, num } = useI18n();
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(1);
  const [confirm, setConfirm] = useState(false);
  const ids = useId();
  const upd = (body: Parameters<typeof channelsApi.update>[1]) => run(() => channelsApi.update(c.id, body));
  return (
    <li className="chan-item">
      <div className="chan-head">
        <Avatar c={c} />
        <div className="chan-name">
          <b dir="auto">{c.name || c.handle}</b>
          <span className="chan-tags">
            <span className="chip chip-outline">{PLATFORM_NAME[c.platform]}</span>
            {c.live && (
              <span className="chip chip-danger">
                <span className="dot pulse" /> {t("chan.live")}
              </span>
            )}
            {!c.own && <span className="chip chip-gold">{t("chan.not_mine")}</span>}
            {c.auto_publish && <span className="chip chip-success">{t("chan.auto_publish_on")}</span>}
          </span>
          <span className="muted chan-status">{statusLine(c, view, t, lang)}</span>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          aria-expanded={open}
          aria-controls={`${ids}-opts`}
          onClick={() => setOpen(!open)}
        >
          <Icon name="settings" size={14} /> {t("chan.options")}
        </button>
      </div>
      {!c.own && <OtherNote />}
      {open && (
        <div className="chan-opts" id={`${ids}-opts`}>
          <div className="chan-grid">
            <label>
              <span className="field-label">{t("easy.content_type")}</span>
              <select className="select" value={c.mode} onChange={(e) => upd({ mode: e.target.value as ChannelInfo["mode"] })}>
                {MODES.map((m) => (
                  <option key={m} value={m}>
                    {m === "auto" ? t("easy.mode_auto") : t(`mode.${m}`)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="field-label">{t("chan.game")}</span>
              <select className="select" value={c.game} onChange={(e) => upd({ game: e.target.value })}>
                {view.games.map((g) => (
                  <option key={g} value={g}>
                    {g === "auto" ? t("chan.game_auto") : g === "other" ? t("game.other") : (view.game_names[g] ?? g)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="field-label">{t("chan.keep")}</span>
              <select className="select" value={String(c.keep_days)} onChange={(e) => upd({ keep_days: Number(e.target.value) })}>
                {KEEP.map((d) => (
                  <option key={d} value={String(d)}>
                    {d === -1 ? t("chan.keep_forever") : d === 0 ? t("chan.keep_now") : t("chan.keep_days", { n: num(d) })}
                  </option>
                ))}
              </select>
            </label>
            {c.platform === "youtube" && (
              <label>
                <span className="field-label">{t("chan.yt_kinds")}</span>
                <select className="select" value={c.yt_kinds} onChange={(e) => upd({ yt_kinds: e.target.value as ChannelInfo["yt_kinds"] })}>
                  <option value="both">{t("chan.yt_both")}</option>
                  <option value="live">{t("chan.yt_live")}</option>
                  <option value="uploads">{t("chan.yt_uploads")}</option>
                </select>
              </label>
            )}
          </div>
          <div className="toggle-line">
            <span>
              <b>{t("chan.auto_publish")}</b>
              <span className="muted ez-hint">{c.own ? t("chan.auto_publish_hint") : t("chan.auto_publish_theirs")}</span>
            </span>
            <Toggle checked={c.auto_publish} onChange={(v) => upd({ auto_publish: v })} label={t("chan.auto_publish")} />
          </div>
          <div className="toggle-line">
            <span>
              <b>{t("chan.own_label")}</b>
            </span>
            <Toggle checked={c.own} onChange={(v) => upd({ own: v })} label={t("chan.own_label")} />
          </div>
          <div className="toggle-line">
            <span>
              <b>{t("chan.watching")}</b>
              <span className="muted ez-hint">{t("chan.watching_hint")}</span>
            </span>
            <Toggle checked={c.enabled} onChange={(v) => upd({ enabled: v })} label={t("chan.watching")} />
          </div>
          <div className="chan-actions">
            <button type="button" className="btn btn-sm" onClick={() => run(() => channelsApi.check(c.id), t("chan.checked_now"))}>
              <Icon name="refresh" size={14} /> {t("chan.check_now")}
            </button>
            {c.can_import > 0 && (
              <span className="chan-import">
                <label className="sr-only" htmlFor={`${ids}-n`}>{t("chan.import_count")}</label>
                <select id={`${ids}-n`} className="select" value={String(count)} onChange={(e) => setCount(Number(e.target.value))}>
                  {[1, 2, 3, 5, 10].filter((n) => n <= Math.max(1, c.can_import)).map((n) => (
                    <option key={n} value={String(n)}>{num(n)}</option>
                  ))}
                </select>
                <button type="button" className="btn btn-sm"
                  onClick={() => run(() => channelsApi.importRecent(c.id, count), t("chan.import_queued"))}>
                  <Icon name="download" size={14} /> {t("chan.import_recent", { n: num(count) })}
                </button>
              </span>
            )}
            {confirm ? (
              <span className="chan-confirm">
                <span>{t("chan.remove_confirm")}</span>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => run(() => channelsApi.remove(c.id), t("chan.removed"))}>
                  {t("chan.remove")}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setConfirm(false)}>
                  {t("common.cancel")}
                </button>
              </span>
            ) : (
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setConfirm(true)}>
                <Icon name="trash" size={14} /> {t("chan.remove")}
              </button>
            )}
          </div>
          {c.last_error && <p className="muted chan-err" dir="auto">{c.last_error}</p>}
        </div>
      )}
    </li>
  );
}

// =========================================================================== Settings card

export function ChannelsCard({ easy }: { easy?: boolean }) {
  const { t, num } = useI18n();
  const { view, run } = useChannels(20000);
  const loaded = !!view;
  useEffect(() => {
    // the Easy home card links to #/settings/channels
    if (loaded && /\/channels$/.test(window.location.hash)) document.getElementById("channels")?.scrollIntoView({ block: "start" });
  }, [loaded]);
  if (!view) return null;
  const s = view.settings;
  const recent = view.vods.slice(0, easy ? 6 : 12);
  const body = (
    <div className="chan-body">
      <AddChannel run={run} easy={false} />
      {view.channels.length > 0 && (
        <ul className="chan-list" aria-label={t("chan.title")}>
          {view.channels.map((c) => (
            <ChannelItem key={c.id} c={c} view={view} run={run} />
          ))}
        </ul>
      )}
      {recent.length > 0 && (
        <div className="chan-recent">
          <h3>{t("chan.recent")}</h3>
          <ul className="chan-vods">
            {recent.map((v) => (
              <VodRow key={v.key} v={v} run={run} showChannel={view.channels.length > 1} />
            ))}
          </ul>
        </div>
      )}
      {view.channels.length > 0 && (
        <div className="chan-global">
          <div className="toggle-line">
            <span>
              <b>{t("chan.pause_metered")}</b>
              <span className="muted ez-hint">{t("chan.pause_metered_hint")}</span>
            </span>
            <Toggle checked={s.pause_metered} onChange={(v) => run(() => channelsApi.settings({ pause_metered: v }))} label={t("chan.pause_metered")} />
          </div>
          <div className="toggle-line">
            <span>
              <b>{t("chan.pause_games")}</b>
              <span className="muted ez-hint">{t("chan.pause_games_hint")}</span>
            </span>
            <Toggle checked={s.pause_games} onChange={(v) => run(() => channelsApi.settings({ pause_games: v }))} label={t("chan.pause_games")} />
          </div>
          {!easy && (
            <label className="chan-free">
              <span className="field-label">{t("chan.min_free")}</span>
              <select className="select" value={String(s.min_free_gb)} onChange={(e) => run(() => channelsApi.settings({ min_free_gb: Number(e.target.value) }))}>
                {[2, 5, 10, 20, 50, 100].concat([s.min_free_gb]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map((g) => (
                  <option key={g} value={String(g)}>{t("chan.gb", { n: num(g) })}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      )}
    </div>
  );
  if (easy)
    return (
      <section className="card ez-set-card" id="channels" aria-labelledby="ez-set-chan">
        <h2 id="ez-set-chan">{t("chan.title")}</h2>
        <p className="muted" style={{ marginTop: 0 }}>{t("chan.desc")}</p>
        {body}
      </section>
    );
  return (
    <section className="card setting" id="channels">
      <div>
        <h2>{t("chan.title")}</h2>
        <p>{t("chan.desc")}</p>
        <p className="chan-how">{t("chan.how")}</p>
      </div>
      {body}
    </section>
  );
}

// =========================================================================== Easy home card

export function ConnectChannelCard() {
  const { t, lang } = useI18n();
  const { view, run } = useChannels(30000);
  const [open, setOpen] = useState(false);
  if (!view) return null;
  if (view.channels.length === 0)
    return (
      <section className="card ez-chan-card" aria-labelledby="ez-chan-title">
        <div className="ez-chan-top">
          <span className="ez-chan-icon" aria-hidden="true">
            <Icon name="zap" size={18} />
          </span>
          <div className="ez-chan-text">
            <h2 id="ez-chan-title">{t("chan.connect_title")}</h2>
            <p className="muted">{t("chan.connect_lede")}</p>
          </div>
          {!open && (
            <button type="button" className="btn btn-primary" onClick={() => setOpen(true)}>
              <Icon name="link" /> {t("chan.connect")}
            </button>
          )}
        </div>
        {open && <AddChannel run={run} easy />}
      </section>
    );
  return (
    <section className="card ez-chan-card" aria-labelledby="ez-chan-title">
      <h2 id="ez-chan-title" className="sr-only">{t("chan.title")}</h2>
      <ul className="ez-chan-list">
        {view.channels.map((c) => (
          <li key={c.id} className="ez-chan-row">
            <Avatar c={c} />
            <span className="ez-chan-text">
              <b dir="auto">{c.name || c.handle}</b>
              <span className="muted">
                {PLATFORM_NAME[c.platform]} · {statusLine(c, view, t, lang)}
              </span>
            </span>
            {c.live && (
              <span className="chip chip-danger">
                <span className="dot pulse" /> {t("chan.live")}
              </span>
            )}
          </li>
        ))}
      </ul>
      <a className="link-btn" href={`${href.settings}/channels`}>
        {t("chan.manage")}
      </a>
    </section>
  );
}

// =========================================================================== Library line

export function ChannelSource({ c }: { c: ChannelLine | null | undefined }) {
  const { t } = useI18n();
  if (!c || !c.name) return null;
  const plat = c.platform ? PLATFORM_NAME[c.platform] : "";
  return (
    <span className="chan-src" title={t("chan.from_title")}>
      <Icon name="zap" size={11} />
      <span dir="auto">{[plat, c.name, c.stream_title].filter(Boolean).join(" · ")}</span>
    </span>
  );
}
