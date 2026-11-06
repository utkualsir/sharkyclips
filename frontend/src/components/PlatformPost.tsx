// 1.2.18: the Easy upload button's platform picker and the TikTok / Reels post flow.
import { useEffect, useRef, useState } from "react";
import type { PlatformClipState } from "../api";
import { copyText, platformsApi, type Platform, type PlatformAiVoice, type PlatformsOverview, type PostPlatform } from "../extras";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { ProgressBar, Toggle } from "./ui";

const NAMES: Record<Platform, string> = { youtube: "YouTube", tiktok: "TikTok", reels: "Reels" };

let overviewCache: Promise<PlatformsOverview> | null = null;
export function usePlatforms(): PlatformsOverview | null {
  const [o, setO] = useState<PlatformsOverview | null>(null);
  useEffect(() => {
    overviewCache = overviewCache ?? platformsApi.overview();
    overviewCache.then(setO).catch(() => {
      overviewCache = null;
    });
  }, []);
  return o;
}

export function PlatformPicker({ value, onChange }: { value: Platform; onChange: (p: Platform) => void }) {
  const { t } = useI18n();
  return (
    <div className="ez-when ez-platforms" role="radiogroup" aria-label={t("platform.pick")}>
      {(["youtube", "tiktok", "reels"] as Platform[]).map((p) => (
        <button key={p} type="button" role="radio" aria-checked={value === p} onClick={() => onChange(p)}>
          {NAMES[p]}
        </button>
      ))}
    </div>
  );
}

/** 1.2.20: a dubbed clip's switches: the AI-voice line in the caption, and the platform's AI label
 *  (automatic mode) or a reminder to switch it on yourself (semi-automatic). Both on by default. */
export function useAiSwitches(pid: string, cid: string, platform: PostPlatform) {
  const [ai, setAi] = useState<PlatformAiVoice | null>(null);
  const [note, setNote] = useState(true);
  const [label, setLabel] = useState(true);
  useEffect(() => {
    platformsApi.clip(platform, pid, cid).then((r) => setAi(r.ai_voice)).catch(() => {});
  }, [pid, cid, platform]);
  return { ai, note, label, setNote, setLabel, flags: { ai_voice_note: note, ai_label: label } };
}

function PlatformAiSwitches({
  sw,
  names,
  semi,
}: {
  sw: ReturnType<typeof useAiSwitches>;
  names: string;
  semi: boolean | null;
}) {
  const { t } = useI18n();
  if (!sw.ai?.dub) return null;
  const labelText = semi === null ? t("platform.ai_label_mixed", { name: names }) : t(semi ? "platform.ai_label_semi" : "platform.ai_label_api", { name: names });
  return (
    <div className="field ai-voice-box">
      <span className="field-label">
        <Icon name="mic" size={14} /> {t("aivoice.title")}
      </span>
      <div className="toggle-row">
        <Toggle checked={sw.note} onChange={sw.setNote} label={t("platform.ai_note")} />
        <span>{t("platform.ai_note")}</span>
      </div>
      {sw.note && sw.ai.line && (
        <span className="field-hint ai-voice-line" dir="auto">
          “{sw.ai.line}”
        </span>
      )}
      <div className="toggle-row">
        <Toggle checked={sw.label} onChange={sw.setLabel} label={labelText} />
        <span>{labelText}</span>
      </div>
    </div>
  );
}

/** "Post to TikTok" + its state. Semi mode: caption to the clipboard, the upload page opens,
 *  the exported file is shown in Explorer when it's ready. API mode: posts by itself. */
export function PlatformPost({
  pid,
  cid,
  platform,
  state,
  ready,
  overview,
}: {
  pid: string;
  cid: string;
  platform: PostPlatform;
  state: PlatformClipState | undefined;
  ready: boolean;
  overview: PlatformsOverview | null;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const mode = overview?.[platform].mode ?? "semi";
  const name = NAMES[platform];
  const prev = useRef(state?.status);
  const sw = useAiSwitches(pid, cid, platform);

  // the export of a semi-automatic post just finished: show the file
  useEffect(() => {
    const was = prev.current;
    prev.current = state?.status;
    if (was === "exporting" && state?.status === "exported" && state.mode === "semi" && state.file) {
      platformsApi.reveal(state.file).catch(() => {});
      toast({ kind: "ok", text: t("platform.file_ready", { name }), hint: state.file });
    }
    if ((was === "exporting" || was === "uploading") && state?.status === "error") {
      toast({ kind: "err", text: state.error?.message ?? t("platform.failed", { name }), hint: state.error?.hint ?? undefined });
    }
  }, [state?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const post = async () => {
    setBusy(true);
    try {
      const r = await platformsApi.post(platform, pid, cid, sw.ai?.dub ? sw.flags : undefined);
      if (r.mode === "semi") {
        const copied = await copyText(r.caption);
        window.open(r.upload_page, "_blank", "noopener");
        toast({ kind: "info", text: t(copied ? "platform.semi_started" : "platform.semi_started_nocopy", { name }) });
        if (r.ai_voice?.label) toast({ kind: "info", text: t(`platform.ai_remind.${platform}`) });
      } else {
        toast({ kind: "info", text: t("platform.api_started", { name }) });
      }
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const copyAgain = async () => {
    try {
      const r = await platformsApi.clip(platform, pid, cid);
      if (await copyText(r.caption)) toast({ kind: "ok", text: t("common.copied") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const st = state?.status;
  if (st === "exporting" || st === "uploading") {
    return (
      <div className="ez-up-state">
        <span className="ez-up-line">
          <span className="spinner" />{" "}
          {t(st === "exporting" ? "platform.exporting" : "platform.uploading", { name })}
          {state?.progress != null && ` ${num(Math.round(state.progress * 100))}%`}
        </span>
        <ProgressBar value={state?.progress} label={t(st === "exporting" ? "platform.exporting" : "platform.uploading", { name })} />
      </div>
    );
  }
  return (
    <>
      {st === "published" || st === "processing" ? (
        <div className="ez-up-state ez-up-live">
          <Icon name="check" size={18} />
          <span>
            {t(st === "processing" ? "platform.processing" : "platform.posted", { name })}
            {state?.privacy === "self_only" && <span className="ez-hint"> {t("platform.private_note")}</span>}
          </span>
          {state?.url && (
            <a className="btn ez-big" href={state.url} target="_blank" rel="noreferrer">
              <Icon name="eye" /> {t("platform.open", { name })}
            </a>
          )}
        </div>
      ) : (
        <>
          {st === "error" && (
            <p className="ez-up-error" role="alert">
              <Icon name="alert" size={15} /> {state?.error?.message}
            </p>
          )}
          <PlatformAiSwitches sw={sw} names={name} semi={mode === "semi"} />
          <button className="btn btn-primary ez-big" disabled={!ready || busy} onClick={post}>
            {busy ? <span className="spinner" /> : <Icon name="upload" />} {t("platform.post_to", { name })}
          </button>
        </>
      )}
      {st === "exported" && state?.mode === "semi" && state.ai_voice?.label && (
        <p className="ez-hint ai-remind" role="note">
          <Icon name="alert" size={14} /> {t(`platform.ai_remind.${platform}`)}
        </p>
      )}
      {st === "exported" && state?.mode === "semi" && (
        <div className="ez-platform-tools">
          <button type="button" className="link-btn" onClick={() => state.file && platformsApi.reveal(state.file).catch(() => {})}>
            <Icon name="file" size={14} /> {t("platform.show_file")}
          </button>
          <button type="button" className="link-btn" onClick={copyAgain}>
            <Icon name="copy" size={14} /> {t("platform.copy_caption")}
          </button>
          <a className="link-btn" href={overview?.[platform].upload_page ?? "#"} target="_blank" rel="noreferrer">
            <Icon name="link" size={14} /> {t("platform.open_upload", { name })}
          </a>
        </div>
      )}
      <p className="ez-hint ez-mode-note">
        {mode === "api"
          ? t(platform === "tiktok" && !overview?.tiktok.audited ? "platform.mode_api_private" : platform === "reels" && !overview?.reels.audited ? "platform.mode_api_review" : "platform.mode_api", { name })
          : t("platform.mode_semi", { name })}
      </p>
    </>
  );
}

/** Pro mode (publish dialog): "Also post to TikTok / Reels" with the same flow, smaller. */
export function PlatformRow({ pid, cid }: { pid: string; cid: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const overview = usePlatforms();
  const [rec, setRec] = useState<Record<string, { status?: string; privacy?: string; url?: string } | null>>({});
  const [busy, setBusy] = useState<PostPlatform | null>(null);
  const sw = useAiSwitches(pid, cid, "tiktok");
  useEffect(() => {
    (["tiktok", "reels"] as PostPlatform[]).forEach((p) =>
      platformsApi
        .clip(p, pid, cid)
        .then((r) => setRec((x) => ({ ...x, [p]: r.job ? { status: r.job.kind === "platform_export" ? "exporting" : "uploading" } : r.record })))
        .catch(() => {}),
    );
  }, [pid, cid]);
  const post = async (p: PostPlatform) => {
    setBusy(p);
    try {
      const r = await platformsApi.post(p, pid, cid, sw.ai?.dub ? sw.flags : undefined);
      if (r.mode === "semi") {
        const copied = await copyText(r.caption);
        window.open(r.upload_page, "_blank", "noopener");
        toast({ kind: "info", text: t(copied ? "platform.semi_started" : "platform.semi_started_nocopy", { name: NAMES[p] }) });
        if (r.ai_voice?.label) toast({ kind: "info", text: t(`platform.ai_remind.${p}`) });
      } else {
        toast({ kind: "info", text: t("platform.api_started", { name: NAMES[p] }) });
      }
      setRec((x) => ({ ...x, [p]: { status: "exporting" } }));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(null);
  };
  return (
    <fieldset className="field">
      <legend className="field-label">{t("platform.also")}</legend>
      <PlatformAiSwitches
        sw={sw}
        names="TikTok / Reels"
        semi={overview && overview.tiktok.mode === overview.reels.mode ? overview.tiktok.mode === "semi" : null}
      />
      <div className="inline-row" style={{ flexWrap: "wrap" }}>
        {(["tiktok", "reels"] as PostPlatform[]).map((p) => {
          const st = rec[p]?.status;
          return (
            <button key={p} type="button" className="btn btn-sm" disabled={busy !== null || st === "exporting" || st === "uploading"} onClick={() => post(p)}>
              {busy === p || st === "exporting" || st === "uploading" ? <span className="spinner" /> : <Icon name={st === "published" ? "check" : "upload"} />}{" "}
              {t("platform.post_to", { name: NAMES[p] })}
            </button>
          );
        })}
      </div>
      <span className="field-hint">
        {(["tiktok", "reels"] as PostPlatform[])
          .map((p) => `${NAMES[p]}: ${overview?.[p].mode === "api" ? t("platform.now_api") : t("platform.now_semi")}`)
          .join(" · ")}
      </span>
    </fieldset>
  );
}
