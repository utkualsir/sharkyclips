// 1.2.36: one "Publish" button with three platform switches (YouTube · Instagram · TikTok).
// Easy card: one tap posts everywhere when nothing needs fixing (the preview opens by itself when
// something does). Pro dialog + Library: the full preview per platform (phone frame), editable
// texts with the platform limits, problems with one-tap fixes, TikTok's required post screen,
// "Post now" or "Plan". Status badges per platform with Retry for the one that failed.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, urls } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import {
  busyState,
  byHand,
  openHandoff,
  publishApi,
  TARGET_NAME,
  TARGETS,
  todo,
  type ClipPosts,
  type PostState,
  type Problem,
  type PublishView,
  type Target,
  type TikTokSettings,
} from "../multipost";
import { useToast } from "../toast";
import { accountsChanged, ConnectDialog, useAccounts } from "./Accounts";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { Modal, ProgressBar, Segmented, Toggle } from "./ui";

const ORDER: Target[] = ["youtube", "reels", "tiktok"];
const PRIVACY_KEYS: Record<string, string> = {
  PUBLIC_TO_EVERYONE: "mp.tt_privacy_public",
  MUTUAL_FOLLOW_FRIENDS: "mp.tt_privacy_friends",
  FOLLOWER_OF_CREATOR: "mp.tt_privacy_followers",
  SELF_ONLY: "mp.tt_privacy_self",
};

// ------------------------------------------------------------------ remembered switches

let targetsCache: Promise<Target[]> | null = null;
export function useTargets(): [Target[], (t: Target[]) => void] {
  const [v, setV] = useState<Target[]>(TARGETS);
  useEffect(() => {
    targetsCache = targetsCache ?? publishApi.targets().then((r) => r.targets);
    targetsCache.then(setV).catch(() => (targetsCache = null));
    const on = (e: Event) => setV((e as CustomEvent<Target[]>).detail);
    window.addEventListener("sc-targets", on);
    return () => window.removeEventListener("sc-targets", on);
  }, []);
  const set = useCallback((t: Target[]) => {
    const sorted = TARGETS.filter((p) => t.includes(p));
    targetsCache = Promise.resolve(sorted);
    window.dispatchEvent(new CustomEvent("sc-targets", { detail: sorted }));
    publishApi.setTargets(sorted).catch(() => {});
  }, []);
  return [v, set];
}

export function TargetSwitches({
  value,
  onChange,
  posts,
  compact,
}: {
  value: Target[];
  onChange: (t: Target[]) => void;
  posts?: ClipPosts | null;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const [acc] = useAccounts();
  return (
    <div className={`mp-switches${compact ? " compact" : ""}`} role="group" aria-label={t("mp.where")}>
      {ORDER.map((p) => {
        const on = value.includes(p);
        const done = posts?.[p]?.status === "published";
        const off = acc && acc[p].mode !== "semi" && !acc[p].connected; // by hand needs no account
        return (
          <button
            key={p}
            type="button"
            className={`mp-switch pf-accent-${p}${on ? " on" : ""}`}
            aria-pressed={on}
            title={off ? t("mp.not_connected_short", { name: TARGET_NAME[p] }) : TARGET_NAME[p]}
            onClick={() => onChange(on ? value.filter((x) => x !== p) : [...value, p])}
          >
            <PlatformIcon p={p} size={compact ? 20 : 18} />
            <span className={compact ? "visually-hidden" : "mp-switch-name"}>{TARGET_NAME[p]}</span>
            {done ? <Icon name="check" size={13} /> : off ? <span className="mp-switch-warn" aria-hidden="true">!</span> : null}
          </button>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ status badges

function relWhen(iso: string | null | undefined, lang: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(lang, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function PostBadge({ s, pid, cid, onChanged }: { s: PostState; pid: string; cid: string; onChanged?: () => void }) {
  const { t, num, lang } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const p = s.platform;
  const name = TARGET_NAME[p];
  let text: string;
  switch (s.status) {
    case "published":
      text = s.views != null ? t("mp.views", { n: num(s.views) }) : s.locked ? t("mp.st_private") : t("mp.st_published");
      break;
    case "scheduled":
      text = t("mp.st_scheduled", { when: relWhen(s.publish_at, lang) });
      break;
    case "preparing":
      text = t("mp.st_preparing");
      break;
    case "uploading":
      text = s.progress != null ? t("mp.st_uploading_pct", { p: num(Math.round(s.progress * 100)) }) : t("mp.st_uploading");
      break;
    case "processing":
      text = t("mp.st_processing");
      break;
    case "ready":
      text = t("mp.st_ready");
      break;
    case "failed":
      text = s.next_try_at ? t("mp.st_retrying") : t("mp.st_failed");
      break;
    case "cancelled":
      text = t("mp.st_cancelled");
      break;
    default:
      text = t("mp.st_idle");
  }
  const retry = async () => {
    setBusy(true);
    try {
      await publishApi.retry(pid, cid, p);
      onChanged?.();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const label = `${name}: ${text}`;
  const inner = (
    <>
      <PlatformIcon p={p} size={15} />
      {busyState(s.status) ? <span className="spinner spinner-xs" aria-hidden="true" /> : s.status === "published" ? <Icon name="check" size={12} /> : s.status === "failed" ? <Icon name="alert" size={12} /> : s.status === "scheduled" ? <Icon name="clock" size={12} /> : null}
      <span className="mp-badge-text">{text}</span>
    </>
  );
  return (
    <span className={`mp-badge mp-st-${s.status} pf-accent-${p}`} title={s.error ? `${s.error.message}${s.error.hint ? ` — ${s.error.hint}` : ""}` : label}>
      {s.url && s.status === "published" ? (
        <a href={s.url} target="_blank" rel="noreferrer" aria-label={t("mp.open_on", { name })}>
          {inner}
        </a>
      ) : (
        <span role="status" aria-label={label}>
          {inner}
        </span>
      )}
      {s.status === "ready" && (
        <button type="button" className="mp-badge-act mp-badge-go" onClick={() => openHandoff({ pid, cid, platforms: [p] })}
          aria-label={t("mp.share_now_on", { name })} title={t("mp.share_now_on", { name })}>
          <Icon name="copy" size={12} />
        </button>
      )}
      {(s.status === "failed" || s.status === "cancelled") && (
        <button type="button" className="mp-badge-act" disabled={busy} onClick={retry} aria-label={t("mp.retry_on", { name })}>
          {busy ? <span className="spinner spinner-xs" /> : <Icon name="refresh" size={12} />}
        </button>
      )}
    </span>
  );
}

export function PostBadges({ posts, pid, cid, onChanged, all }: { posts: ClipPosts | null | undefined; pid: string; cid: string; onChanged?: () => void; all?: boolean }) {
  const { t, num } = useI18n();
  if (!posts) return null;
  const shown = ORDER.filter((p) => all || posts[p].status !== "idle");
  if (!shown.length) return null;
  const tt = posts.tiktok;
  return (
    <div className="mp-badges">
      {shown.map((p) => (
        <PostBadge key={p} s={posts[p]} pid={pid} cid={cid} onChanged={onChanged} />
      ))}
      {posts.everywhere && (
        <span className="mp-everywhere" title={t("mp.everywhere")}>
          <Icon name="check" size={12} /> {t("mp.everywhere")}
        </span>
      )}
      {posts.total_views != null && shown.filter((p) => posts[p].views != null).length > 1 && (
        <span className="mp-total">{t("mp.total_views", { n: num(posts.total_views) })}</span>
      )}
      {tt.make_public_url && (
        <a className="mp-make-public" href={tt.make_public_url} target="_blank" rel="noreferrer">
          <PlatformIcon p="tiktok" size={13} /> {t("mp.tt_make_public")}
        </a>
      )}
      {ORDER.filter((p) => posts[p].status === "failed" && posts[p].error).map((p) => (
        <p key={p} className="mp-fail-line" role="alert">
          <PlatformIcon p={p} size={13} /> {posts[p].error!.message}
          {posts[p].error!.hint && <span className="muted"> {posts[p].error!.hint}</span>}
        </p>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ problems

function problemText(p: Problem, t: (k: string, v?: Record<string, string | number>) => string): string {
  const name = p.platform === "all" ? "" : TARGET_NAME[p.platform];
  return t(`mp.p_${p.code}`, { ...p.params, name, max: p.params.max ?? "", n: p.params.n ?? "" });
}

const FIX_SERVER = ["shorten_title", "shorten_caption", "trim_hashtags", "shorten_description", "no_branded", "fix_branded"];

function Problems({
  view,
  onFix,
  onConnect,
  onTurnOff,
  onPlan,
  onFocusTikTok,
}: {
  view: PublishView;
  onFix: (p: Problem) => void;
  onConnect: (p: Target) => void;
  onTurnOff: (p: Target) => void;
  onPlan: () => void;
  onFocusTikTok: () => void;
}) {
  const { t } = useI18n();
  if (!view.problems.length) return null;
  return (
    <ul className="mp-problems" aria-label={t("mp.problems")}>
      {view.problems.map((p, i) => (
        <li key={`${p.platform}-${p.code}-${i}`} className="mp-problem">
          {p.platform !== "all" ? <PlatformIcon p={p.platform} size={15} /> : <Icon name="alert" size={15} />}
          <span className="mp-problem-text">{problemText(p, t)}</span>
          {p.fix === "connect" && p.platform !== "all" && (
            <button type="button" className="btn btn-sm" onClick={() => onConnect(p.platform as Target)}>
              {t("mp.fix_connect")}
            </button>
          )}
          {p.fix && FIX_SERVER.includes(p.fix) && (
            <button type="button" className="btn btn-sm" onClick={() => onFix(p)}>
              <Icon name="wand" size={14} /> {t(`mp.fix_${p.fix}`)}
            </button>
          )}
          {(p.fix === "turn_off" || p.fix === "connect") && p.platform !== "all" && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => onTurnOff(p.platform as Target)}>
              {t("mp.fix_turn_off", { name: TARGET_NAME[p.platform as Target] })}
            </button>
          )}
          {p.fix === "plan" && (
            <button type="button" className="btn btn-sm" onClick={onPlan}>
              <Icon name="calendar" size={14} /> {t("mp.fix_plan")}
            </button>
          )}
          {(p.fix === "choose_privacy" || p.fix === "choose_disclosure") && (
            <button type="button" className="btn btn-sm" onClick={onFocusTikTok}>
              {t("mp.fix_choose")}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ preview per platform

function Counter({ n, max }: { n: number; max: number }) {
  return <span className={`mp-count${n > max ? " over" : ""}`}>{n}/{max}</span>;
}

function hashtags(text: string): number {
  return (text.match(/(?<![\w#])#[^\s#]+/g) || []).length;
}

function Phone({ p, view, video, handle }: { p: Target; view: PublishView; video?: string | null; handle: string | null }) {
  const { t } = useI18n();
  const d = view.drafts;
  const [noVideo, setNoVideo] = useState(!video);
  const text = p === "youtube" ? d.youtube.title : d[p].caption;
  return (
    <div className={`mp-phone pf-accent-${p}`} aria-hidden="true">
      <div className="mp-screen">
        {video && !noVideo ? (
          <video src={`${video}#t=${(view.cover_ms / 1000).toFixed(2)}`} muted playsInline preload="metadata" onError={() => setNoVideo(true)} />
        ) : (
          <div className="mp-screen-ph">
            <PlatformIcon p={p} size={30} />
          </div>
        )}
        <div className={`mp-ui mp-ui-${p}`}>
          <span className="mp-ui-top">{p === "youtube" ? "Shorts" : p === "reels" ? "Reels" : t("mp.tt_for_you")}</span>
          <div className="mp-ui-rail">
            <span />
            <span />
            <span />
          </div>
          <div className="mp-ui-bottom">
            <b>@{(handle || "you").replace(/^@/, "")}</b>
            <span className="mp-ui-cap" dir="auto">
              {text}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LengthChip({ p, view }: { p: Target; view: PublishView }) {
  const { t } = useI18n();
  const max = p === "tiktok" && view.tiktok?.ok ? view.tiktok.max_seconds ?? view.limits.tiktok.max_seconds : view.limits[p].max_seconds;
  const ok = view.duration <= max + 0.05 && view.duration >= view.limits[p].min_seconds;
  return (
    <span className={`mp-chip${ok ? "" : " bad"}`}>
      <Icon name={ok ? "check" : "alert"} size={12} /> {t("mp.length", { dur: fmtTime(view.duration), max: fmtTime(max) })}
    </span>
  );
}

function Editor({
  p,
  view,
  onSave,
}: {
  p: Target;
  view: PublishView;
  onSave: (drafts: Record<string, unknown>) => void;
}) {
  const { t } = useI18n();
  const d = view.drafts;
  const [title, setTitle] = useState(d.youtube.title);
  const [desc, setDesc] = useState(d.youtube.description);
  const [cap, setCap] = useState(p === "youtube" ? "" : d[p].caption);
  useEffect(() => {
    setTitle(d.youtube.title);
    setDesc(d.youtube.description);
    if (p !== "youtube") setCap(d[p].caption);
  }, [d, p]);
  if (p === "youtube") {
    return (
      <div className="mp-fields">
        <label className="field">
          <span className="field-label">
            {t("mp.yt_title")} <Counter n={title.length} max={view.limits.youtube.title} />
          </span>
          <input className="input" dir="auto" value={title} onChange={(e) => setTitle(e.target.value)}
            onBlur={() => title !== d.youtube.title && onSave({ youtube: { title } })} />
        </label>
        <label className="field">
          <span className="field-label">{t("mp.yt_description")}</span>
          <textarea className="input" dir="auto" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)}
            onBlur={() => desc !== d.youtube.description && onSave({ youtube: { description: desc } })} />
        </label>
        <details className="mp-full">
          <summary>
            {t("mp.yt_full")} <Counter n={d.youtube.full_description.length} max={view.limits.youtube.description} />
          </summary>
          <pre dir="auto">{d.youtube.full_description}</pre>
          {d.youtube.tags.length > 0 && <p className="field-hint">{t("mp.yt_tags", { tags: d.youtube.tags.join(", ") })}</p>}
        </details>
      </div>
    );
  }
  const lim = view.limits[p];
  return (
    <div className="mp-fields">
      <label className="field">
        <span className="field-label">
          {t("mp.caption")} <Counter n={cap.length} max={lim.caption} />
          {p === "reels" && (
            <>
              {" "}
              <span className="mp-count-sep">·</span> <Counter n={hashtags(cap)} max={view.limits.reels.hashtags} /> #
            </>
          )}
        </span>
        <textarea className="input" dir="auto" rows={6} value={cap} onChange={(e) => setCap(e.target.value)}
          onBlur={() => cap !== d[p].caption && onSave({ [p]: { caption: cap } })} />
      </label>
      {d[p].edited && (
        <button type="button" className="link-btn field-hint" onClick={() => onSave({ [p]: { caption: null } })}>
          <Icon name="refresh" size={12} /> {t("mp.reset_caption")}
        </button>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ TikTok's post screen

function TikTokPanel({ view, onSet, innerRef }: { view: PublishView; onSet: (s: Partial<TikTokSettings>) => void; innerRef?: React.Ref<HTMLFieldSetElement> }) {
  const { t } = useI18n();
  const tt = view.tiktok;
  if (!tt) return null;
  if (!tt.ok) {
    return tt.error ? (
      <p className="mp-problem" role="alert">
        <PlatformIcon p="tiktok" size={15} /> {tt.error.message} {tt.error.hint && <span className="muted">{tt.error.hint}</span>}
      </p>
    ) : null;
  }
  const s = tt.settings!;
  const privacy = tt.privacy ?? "";
  const branded = s.disclose && s.brand_content;
  return (
    <fieldset className="mp-tt" ref={innerRef}>
      <legend>
        <PlatformIcon p="tiktok" size={16} /> {t("mp.tt_settings")}
      </legend>
      <p className="mp-tt-who">
        {t("mp.tt_posting_as")} <b>@{tt.creator?.username}</b>
        {tt.creator?.nickname && <span className="muted"> ({tt.creator.nickname})</span>}
      </p>
      <label className="field">
        <span className="field-label">{t("mp.tt_privacy")}</span>
        <select
          className="select"
          value={privacy}
          disabled={!tt.audited}
          onChange={(e) => onSet({ privacy: e.target.value || null })}
          aria-describedby={!tt.audited ? "mp-tt-self" : undefined}
        >
          {tt.audited && <option value="">{t("mp.tt_privacy_pick")}</option>}
          {(tt.privacy_options ?? []).map((o) => (
            <option
              key={o}
              value={o}
              disabled={o === "SELF_ONLY" && branded}
              title={o === "SELF_ONLY" && branded ? t("mp.tt_branded_private") : undefined}
            >
              {t(PRIVACY_KEYS[o] ?? o)}
            </option>
          ))}
        </select>
        {!tt.audited && (
          <span className="field-hint" id="mp-tt-self">
            {t("mp.tt_self_only")}
          </span>
        )}
      </label>
      <div className="mp-tt-allow">
        <span className="field-label">{t("mp.tt_allow")}</span>
        {(
          [
            ["allow_comment", "comment_disabled", "mp.tt_comments"],
            ["allow_duet", "duet_disabled", "mp.tt_duet"],
            ["allow_stitch", "stitch_disabled", "mp.tt_stitch"],
          ] as const
        ).map(([k, dis, label]) => (
          <label key={k} className={`mp-check${tt[dis] ? " disabled" : ""}`}>
            <input type="checkbox" checked={!tt[dis] && s[k]} disabled={!!tt[dis]} onChange={(e) => onSet({ [k]: e.target.checked })} />
            <span>
              {t(label)}
              {tt[dis] && <span className="muted"> {t("mp.tt_off_in_app")}</span>}
            </span>
          </label>
        ))}
      </div>
      <div className="mp-tt-disclose">
        <div className="toggle-row">
          <Toggle checked={s.disclose} onChange={(v) => onSet({ disclose: v })} label={t("mp.tt_disclose")} />
          <span>
            {t("mp.tt_disclose")}
            <span className="field-hint" style={{ display: "block" }}>
              {t("mp.tt_disclose_hint")}
            </span>
          </span>
        </div>
        {s.disclose && (
          <div className="mp-tt-brand">
            <label className="mp-check">
              <input type="checkbox" checked={s.brand_organic} onChange={(e) => onSet({ brand_organic: e.target.checked })} />
              <span>
                {t("mp.tt_your_brand")}
                <span className="field-hint" style={{ display: "block" }}>
                  {t("mp.tt_your_brand_hint")}
                </span>
              </span>
            </label>
            <label className={`mp-check${privacy === "SELF_ONLY" ? " disabled" : ""}`}>
              <input type="checkbox" checked={s.brand_content} disabled={privacy === "SELF_ONLY"} onChange={(e) => onSet({ brand_content: e.target.checked })} />
              <span>
                {t("mp.tt_branded")}
                <span className="field-hint" style={{ display: "block" }}>
                  {privacy === "SELF_ONLY" ? t("mp.tt_branded_private") : t("mp.tt_branded_hint")}
                </span>
              </span>
            </label>
            {(s.brand_organic || s.brand_content) && (
              <p className="field-hint mp-tt-label">
                {t(s.brand_content ? "mp.tt_label_paid" : "mp.tt_label_promo")}
              </p>
            )}
          </div>
        )}
      </div>
    </fieldset>
  );
}

export function TikTokDeclaration({ view, branded }: { view?: PublishView | null; branded?: boolean }) {
  const { t } = useI18n();
  const music = view?.tiktok?.music_url ?? "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en";
  const bc = view?.tiktok?.branded_url ?? "https://www.tiktok.com/legal/page/global/bc-policy/en";
  return (
    <p className="mp-declare">
      <PlatformIcon p="tiktok" size={13} />{" "}
      {branded ? (
        <>
          {t("mp.tt_declare_bc_a")}{" "}
          <a href={bc} target="_blank" rel="noreferrer">
            {t("mp.tt_bc_policy")}
          </a>{" "}
          {t("mp.tt_declare_and")}{" "}
          <a href={music} target="_blank" rel="noreferrer">
            {t("mp.tt_music")}
          </a>
          {t("mp.tt_declare_end")}
        </>
      ) : (
        <>
          {t("mp.tt_declare_a")}{" "}
          <a href={music} target="_blank" rel="noreferrer">
            {t("mp.tt_music")}
          </a>
          {t("mp.tt_declare_end")}
        </>
      )}
    </p>
  );
}

// ------------------------------------------------------------------ when

type When = "now" | "plan" | "auto";

function localInput(d: Date) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 16);
}

function WhenPicker({
  when,
  setWhen,
  at,
  setAt,
  social,
  lead,
}: {
  when: When;
  setWhen: (w: When) => void;
  at: string;
  setAt: (v: string) => void;
  social: boolean;
  lead: number;
}) {
  const { t } = useI18n();
  return (
    <div className="mp-when">
      <Segmented<When>
        value={when}
        label={t("mp.when")}
        onChange={setWhen}
        options={[
          { value: "now", label: t("mp.when_now") },
          { value: "plan", label: t("mp.when_plan") },
          { value: "auto", label: t("mp.when_auto") },
        ]}
      />
      {when === "plan" && (
        <input
          className="input"
          type="datetime-local"
          value={at}
          min={localInput(new Date(Date.now() + (lead + 60) * 1000))}
          aria-label={t("mp.when_plan")}
          onChange={(e) => setAt(e.target.value)}
        />
      )}
      {when !== "now" && social && (
        <p className="field-hint mp-pc-on">
          <Icon name="power" size={12} /> {t("mp.pc_on")}
        </p>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ the dialog

function useView(pid: string, cid: string, targets: Target[]) {
  const [view, setView] = useState<PublishView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const key = targets.join(",");
  const load = useCallback(() => {
    publishApi
      .view(pid, cid, targets)
      .then((v) => {
        setView(v);
        setErr(null);
      })
      .catch((e) => setErr(e.message));
  }, [pid, cid, key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  return { view, setView, err, load };
}

function summary(r: Awaited<ReturnType<typeof publishApi.start>>, t: (k: string, v?: Record<string, string | number>) => string): string {
  const parts = Object.entries(r.results).map(([p, x]) =>
    `${TARGET_NAME[p as Target]}: ${t(x?.error ? "mp.st_failed" : x?.mode === "semi" ? "mp.r_by_hand" : x?.status === "scheduled" ? "mp.r_planned" : x?.skipped ? "mp.r_already" : "mp.r_started")}`,
  );
  return parts.join(" · ");
}

/** After Publish: TikTok's API note, and the by-hand platforms go to the "post it yourself" steps. */
function afterStart(
  r: Awaited<ReturnType<typeof publishApi.start>>,
  targets: Target[],
  pid: string,
  cid: string,
  title: string | undefined,
  t: (k: string, v?: Record<string, string | number>) => string,
  toast: ReturnType<typeof useToast>,
) {
  const tt = r.results.tiktok;
  if (tt && !tt.error && !tt.skipped && tt.mode !== "semi") toast({ kind: "info", text: t("mp.tt_after") });
  const hand = byHand(targets, r.view.modes, r.view.states).filter((p) => !r.results[p]?.error);
  openHandoff({ pid, cid, title, platforms: hand });
}

export function PublishDialog({
  pid,
  cid,
  title,
  video,
  initialWhen = "now",
  onClose,
  onDone,
}: {
  pid: string;
  cid: string;
  title?: string;
  video?: string | null;
  initialWhen?: When;
  onClose: () => void;
  onDone?: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [targets, setTargets] = useTargets();
  const { view, setView, err, load } = useView(pid, cid, targets);
  const [when, setWhen] = useState<When>(initialWhen);
  const [at, setAt] = useState(localInput(new Date(Date.now() + 24 * 3600 * 1000)));
  const [busy, setBusy] = useState(false);
  const [connect, setConnect] = useState<Target | null>(null);
  const [acc] = useAccounts();
  const ttRef = useRef<HTMLFieldSetElement>(null);
  const pending = view ? todo(view.states, targets) : [];
  const branded = !!view?.tiktok?.settings?.disclose && !!view?.tiktok?.settings?.brand_content;
  const ttApi = view?.modes?.tiktok === "api";

  useEffect(() => {
    const on = () => load();
    window.addEventListener("sc-accounts", on);
    window.addEventListener("sc-posts-changed", on);
    return () => {
      window.removeEventListener("sc-accounts", on);
      window.removeEventListener("sc-posts-changed", on);
    };
  }, [load]);

  const save = async (body: { drafts?: Record<string, unknown>; tiktok?: Partial<TikTokSettings> }) => {
    if (body.tiktok) {
      // show the switch at once; the server's answer (problems, rules) follows
      const patch = body.tiktok;
      setView((v) =>
        v?.tiktok?.settings
          ? {
              ...v,
              tiktok: {
                ...v.tiktok,
                settings: { ...v.tiktok.settings, ...patch },
                privacy: v.tiktok.audited && "privacy" in patch ? patch.privacy ?? null : v.tiktok.privacy,
              },
            }
          : v,
      );
    }
    try {
      setView(await publishApi.save(pid, cid, body, targets));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const fix = async (p: Problem) => {
    try {
      setView(await publishApi.fix(pid, cid, p.platform, p.fix!));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const go = async () => {
    if (!view) return;
    setBusy(true);
    try {
      const whenValue = when === "now" ? "now" : when === "auto" ? "auto" : new Date(at).toISOString();
      const r = await publishApi.start(pid, cid, { platforms: targets, when: whenValue, consent: targets.includes("tiktok") });
      setView(r.view);
      toast({ kind: Object.values(r.results).some((x) => x?.error) ? "err" : "ok", text: summary(r, t) });
      afterStart(r, targets, pid, cid, title, t, toast);
      onDone?.();
      if (!Object.values(r.results).some((x) => x?.error)) onClose();
    } catch (e: any) {
      if (e instanceof ApiError && e.code === "problems") load();
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const social = targets.some((p) => p !== "youtube");
  const blocked = !view || !!view.problems.length || !pending.length || busy || (when === "plan" && !at);
  const handle = (p: Target) => (p === "tiktok" ? view?.tiktok?.creator?.username ?? acc?.tiktok.handle : acc?.[p].handle) ?? null;

  return (
    <Modal
      wide
      title={
        <span className="mp-title">
          <Icon name="upload" /> {t("mp.title")}
          {title && <span className="mp-title-clip" dir="auto">{title}</span>}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          {targets.includes("tiktok") && pending.includes("tiktok") && ttApi && <TikTokDeclaration view={view} branded={branded} />}
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" disabled={blocked} onClick={go}>
            {busy ? <span className="spinner" /> : <Icon name={when === "now" ? "upload" : "calendar"} />}{" "}
            {when === "now" ? t("mp.publish_n", { n: pending.length }) : t("mp.plan_n", { n: pending.length })}
          </button>
        </>
      }
    >
      {err && <p className="mp-problem">{err}</p>}
      <TargetSwitches value={targets} onChange={setTargets} posts={view?.states} />
      {view && <PostBadges posts={view.states} pid={pid} cid={cid} onChanged={load} />}
      <WhenPicker when={when} setWhen={setWhen} at={at} setAt={setAt} social={social} lead={view?.lead_s ?? 120} />
      {!view ? (
        <div className="mp-previews">
          {targets.map((p) => (
            <div key={p} className="card skeleton" style={{ height: 300 }} />
          ))}
        </div>
      ) : (
        <>
          {view.source === "rendering" && (
            <p className="field-hint">
              <span className="spinner spinner-xs" /> {t("mp.rendering")}
            </p>
          )}
          <Problems
            view={view}
            onFix={fix}
            onConnect={setConnect}
            onTurnOff={(p) => setTargets(targets.filter((x) => x !== p))}
            onPlan={() => setWhen("auto")}
            onFocusTikTok={() => ttRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })}
          />
          {targets.includes("tiktok") && pending.includes("tiktok") && (
            <TikTokPanel view={view} innerRef={ttRef} onSet={(s) => save({ tiktok: s })} />
          )}
          {view.ai_voice.dub && (
            <p className="field-hint">
              <Icon name="mic" size={12} /> {t("mp.ai_voice")}
            </p>
          )}
          <div className="mp-previews">
            {ORDER.filter((p) => targets.includes(p)).map((p) => (
              <section key={p} className={`mp-preview pf-accent-${p}`} aria-label={TARGET_NAME[p]}>
                <header className="mp-preview-head">
                  <PlatformIcon p={p} size={16} /> <b>{TARGET_NAME[p]}</b>
                  <LengthChip p={p} view={view} />
                  {p !== "youtube" && (
                    <span className={`mp-chip mp-mode-${view.modes?.[p] ?? "semi"}`} title={t(view.modes?.[p] === "api" ? "mp.mode_api_hint" : "mp.mode_semi_hint", { name: TARGET_NAME[p] })}>
                      <Icon name={view.modes?.[p] === "api" ? "zap" : "copy"} size={12} /> {t(view.modes?.[p] === "api" ? "mp.mode_api" : "mp.mode_semi")}
                    </span>
                  )}
                </header>
                <Phone p={p} view={view} video={video} handle={handle(p)} />
                {pending.includes(p) ? <Editor p={p} view={view} onSave={(d) => save({ drafts: d })} /> : <PostBadge s={view.states[p]} pid={pid} cid={cid} onChanged={load} />}
              </section>
            ))}
          </div>
        </>
      )}
      {connect && (
        <ConnectDialog
          p={connect}
          onClose={() => {
            setConnect(null);
            accountsChanged();
            load();
          }}
        />
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ the Easy card's one-tap block

export function PublishBlock({
  pid,
  cid,
  title,
  posts,
  ready,
  hold,
  video,
  when,
  onWhen,
  onChanged,
}: {
  pid: string;
  cid: string;
  title: string;
  posts: ClipPosts | null | undefined;
  ready: boolean;
  hold: boolean;
  video?: string | null;
  when: "now" | "auto";
  onWhen: (w: "now" | "auto") => void;
  onChanged: () => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [targets, setTargets] = useTargets();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [acc] = useAccounts();
  const pending = useMemo(() => todo(posts, targets), [posts, targets]);
  const moving = ORDER.filter((p) => busyState(posts?.[p]?.status));
  const waiting = ORDER.filter((p) => posts?.[p]?.status === "ready");
  useEffect(() => {
    window.addEventListener("sc-posts-changed", onChanged);
    return () => window.removeEventListener("sc-posts-changed", onChanged);
  }, [onChanged]);
  const go = async () => {
    setBusy(true);
    try {
      const v = await publishApi.view(pid, cid, targets);
      if (v.problems.length || (v.tiktok?.ok && v.tiktok.audited && !v.tiktok.privacy && pending.includes("tiktok"))) {
        setOpen(true); // something needs a tap first: the preview shows it
      } else {
        const r = await publishApi.start(pid, cid, { platforms: targets, when, consent: targets.includes("tiktok") });
        toast({ kind: Object.values(r.results).some((x) => x?.error) ? "err" : "ok", text: summary(r, t) });
        afterStart(r, targets, pid, cid, title, t, toast);
        onChanged();
      }
    } catch (e: any) {
      if (e instanceof ApiError && e.code === "problems") setOpen(true);
      else toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  return (
    <div className="mp-block">
      <PostBadges posts={posts} pid={pid} cid={cid} onChanged={onChanged} />
      {waiting.length > 0 && (
        <button type="button" className="btn ez-big mp-resume" onClick={() => openHandoff({ pid, cid, title, platforms: waiting })}>
          <Icon name="copy" /> {t("mp.ho_resume", { names: waiting.map((p) => TARGET_NAME[p]).join(" · ") })}
        </button>
      )}
      {moving.length > 0 && (
        <ProgressBar
          value={moving.length === 1 ? posts?.[moving[0]]?.progress ?? null : null}
          label={t("mp.st_uploading")}
        />
      )}
      {pending.length > 0 && (
        <>
          <TargetSwitches value={targets} onChange={setTargets} posts={posts} compact />
          <div className="mp-go">
            <button className="btn btn-primary ez-big" disabled={!ready || hold || busy || !pending.length} onClick={go}>
              {busy ? <span className="spinner" /> : <Icon name="upload" />} {t("mp.publish")}
              {pending.length < 3 && <span className="mp-go-n"> · {num(pending.length)}</span>}
            </button>
            <button type="button" className="btn btn-ghost ez-big mp-preview-btn" onClick={() => setOpen(true)} disabled={!ready}
              aria-label={t("mp.preview")} title={t("mp.preview")}>
              <Icon name="eye" />
            </button>
          </div>
          <div className="ez-when" role="radiogroup" aria-label={t("easy.when_label")}>
            {(["now", "auto"] as const).map((w) => (
              <button key={w} type="button" role="radio" aria-checked={when === w} onClick={() => onWhen(w)}>
                {t(`easy.when_${w}`)}
              </button>
            ))}
          </div>
          {pending.includes("tiktok") && acc?.tiktok.mode === "api" && <TikTokDeclaration />}
          {when === "auto" && pending.some((p) => p !== "youtube") && <p className="ez-hint">{t("mp.pc_on")}</p>}
        </>
      )}
      {open && (
        <PublishDialog pid={pid} cid={cid} title={title} video={video} initialWhen={when} onClose={() => setOpen(false)} onDone={onChanged} />
      )}
    </div>
  );
}

/** Pro dialog / Library: a "Publish everywhere" button + this clip's badges. */
export function PublishEverywhereButton({
  pid,
  cid,
  title,
  posts,
  small,
  onChanged,
}: {
  pid: string;
  cid: string;
  title?: string;
  posts?: ClipPosts | null;
  small?: boolean;
  onChanged?: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={`btn ${small ? "btn-sm" : ""}`} onClick={() => setOpen(true)}>
        <span className="mp-mini-icons" aria-hidden="true">
          {ORDER.map((p) => (
            <PlatformIcon key={p} p={p} size={small ? 13 : 15} />
          ))}
        </span>
        {posts && todo(posts, TARGETS).length === 0 ? t("mp.view_posts") : t("mp.publish_everywhere")}
      </button>
      {open && (
        <PublishDialog
          pid={pid}
          cid={cid}
          title={title}
          video={urls.clip(pid, cid, "")}
          onClose={() => setOpen(false)}
          onDone={onChanged}
        />
      )}
    </>
  );
}
