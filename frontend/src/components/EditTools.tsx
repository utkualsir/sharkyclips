import { useEffect, useRef, useState } from "react";
import { api, urls, type BleepSound, type BrandState, type ClipOptions, type CutLevel, type EditPlanView, type MemeLevel, type MusicTrack, type ProfanityMode, type ZoomLevel } from "../api";
import { gameReasonLabel } from "../pages/GameDebug";
import { useI18n } from "../i18n";
import { href } from "../router";
import { Icon } from "./Icons";
import { Segmented, Toggle } from "./ui";

const PROFANITY: ProfanityMode[] = ["auto", "bleep", "mute", "off"];
const SOUNDS: BleepSound[] = ["classic", "boop", "custom"];
const CUTS: CutLevel[] = ["off", "light", "strong"];
const ZOOMS: ZoomLevel[] = ["off", "subtle", "strong"];
const MEMES: MemeLevel[] = ["off", "light", "strong"];

interface Props {
  options: ClipOptions;
  setOption: (o: Partial<ClipOptions>) => void;
  plan: EditPlanView | null;
  tracks: MusicTrack[];
  /** this clip's song: undefined = the AI's pick, "" = none, else a file name */
  musicChoice: string | undefined;
  setMusicChoice: (v: string | null) => void;
  brand: BrandState | null;
  hasClip: boolean;
  /** start the loop preview (the end plays into the start, repeating) */
  onLoopPreview?: () => void;
}

/** Instant replay, chat bubbles and meme effects (1.2.17), with what they do on this clip. */
function FunEffects({ options, setOption, plan }: Pick<Props, "options" | "setOption" | "plan">) {
  const { t, num } = useI18n();
  const fx = plan?.fx ?? null;
  const replay = fx?.inserts.find((i) => i.kind === "replay") ?? null;
  const freezes = fx?.inserts.filter((i) => i.kind === "freeze") ?? [];
  const fails = (fx?.shakes.length ?? 0) + (fx?.punches.length ?? 0);
  const off = options.loop;
  return (
    <>
      <div className="render-row">
        <label>{t("fx.replay")}</label>
        <div className="edit-cell">
          <div className="edit-line">
            <Toggle checked={options.replay === "auto"} onChange={(v) => setOption({ replay: v ? "auto" : "off" })} label={t("fx.replay")} />
          </div>
          {options.replay !== "auto" && <span className="edit-note">{t("fx.replay_hint")}</span>}
          {options.replay === "auto" && plan && !off && (
            <span className="edit-note" data-testid="fx-replay">
              {replay
                ? t("fx.replay_of", { what: gameReasonLabel(t, replay.code), s: num(replay.dur, 1) })
                : t("fx.replay_none")}
            </span>
          )}
        </div>
      </div>
      <div className="render-row">
        <label>{t("fx.bubbles")}</label>
        <div className="edit-cell">
          <div className="edit-line">
            <Toggle checked={!!options.chat_bubbles} onChange={(v) => setOption({ chat_bubbles: v })} label={t("fx.bubbles")} />
          </div>
          {!options.chat_bubbles && <span className="edit-note">{t("fx.bubbles_hint")}</span>}
          {options.chat_bubbles && plan && !off && (
            <span className="edit-note">
              {fx?.bubbles.length ? t("fx.bubbles_n", { n: fx.bubbles.length }) : t("fx.bubbles_none")}
            </span>
          )}
        </div>
      </div>
      <div className="render-row">
        <label>{t("fx.memes")}</label>
        <div className="edit-cell">
          <Segmented<MemeLevel>
            value={options.memes ?? "off"}
            options={MEMES.map((m) => ({ value: m, label: t(`fx.memes.${m}`) }))}
            onChange={(m) => setOption({ memes: m })}
            label={t("fx.memes")}
          />
          {(options.memes ?? "off") === "off" && <span className="edit-note">{t("fx.memes_hint")}</span>}
          {(options.memes ?? "off") !== "off" && plan && !off && (
            <span className="edit-note">
              {freezes.length || fails
                ? [
                    ...freezes.map((f) => `“${f.text}”`),
                    ...(fails ? [t("fx.fails_n", { n: fails })] : []),
                  ].join(" · ")
                : t("fx.memes_none")}
            </span>
          )}
        </div>
      </div>
      {off && (options.replay === "auto" || options.chat_bubbles || (options.memes ?? "off") !== "off") && (
        <p className="edit-note warn-text" style={{ margin: "0 0 4px" }}>
          {t("fx.not_in_loop")}
        </p>
      )}
    </>
  );
}

/** Render options of the editing tools (swear words, cuts, zoom, music, brand kit). */
export default function EditTools({ options, setOption, plan, tracks, musicChoice, setMusicChoice, brand, hasClip, onLoopPreview }: Props) {
  const { t, num } = useI18n();
  const seam = plan?.loop ?? null;
  const moved = seam ? Math.round((seam.end - seam.orig_end) * 10) / 10 : 0;
  const bleeps = plan ? (plan.swears ?? []).filter((s) => s.bleep).length : 0;
  const maybes = plan ? (plan.swears ?? []).filter((s) => s.status === "maybe" && !s.bleep).length : 0;
  const [custom, setCustom] = useState<boolean | null>(null);
  const [rev, setRev] = useState(0);
  const player = useRef<HTMLAudioElement | null>(null);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (options.bleep_sound === "custom" && custom == null) api.bleepState().then((b) => setCustom(b.custom)).catch(() => {});
  }, [options.bleep_sound, custom]);
  const listen = (snd: BleepSound) => {
    player.current?.pause();
    player.current = new Audio(urls.bleepPreview(snd, rev));
    player.current.play().catch(() => {});
  };
  const autoCut = plan ? plan.removed.filter((r) => r.kind !== "deleted").reduce((s, r) => s + r.b - r.a, 0) : 0;
  const pulses = plan ? plan.pulses.length : 0;
  const preset = brand?.presets.find((p) => p.id === brand.active) ?? null;
  const analyzed = tracks.filter((x) => x.analyzed);
  const sugg = plan?.suggestion;

  return (
    <div className="edit-tools">
      <div className="render-row">
        <label>{t("edit.profanity")}</label>
        <div className="edit-cell">
          <Segmented<ProfanityMode>
            value={options.profanity}
            options={PROFANITY.map((m) => ({ value: m, label: t(`edit.profanity.${m}`) }))}
            onChange={(m) => setOption({ profanity: m })}
            label={t("edit.profanity")}
          />
          {hasClip && plan && (
            <span className="edit-note">
              {bleeps ? t("edit.bleeps_n", { n: bleeps }) : t("edit.bleeps_none")}
              {maybes > 0 && ` · ${t("edit.maybes_n", { n: maybes })}`}
              {options.profanity === "auto" && ` · ${t("edit.profanity_auto_hint")}`}
            </span>
          )}
          {options.profanity !== "off" && (
            <label className="edit-check">
              <input
                type="checkbox"
                checked={options.profanity_captions}
                onChange={(e) => setOption({ profanity_captions: e.target.checked })}
              />
              {t("edit.mask_captions")}
            </label>
          )}
          {options.profanity !== "off" && options.profanity !== "mute" && (
            <div className="edit-line bleep-sound">
              <select
                className="select select-sm"
                value={options.bleep_sound ?? "classic"}
                onChange={(e) => setOption({ bleep_sound: e.target.value as BleepSound })}
                aria-label={t("edit.bleep_sound")}
              >
                {SOUNDS.map((snd) => (
                  <option key={snd} value={snd}>
                    {t(`edit.bleep_sound.${snd}`)}
                  </option>
                ))}
              </select>
              <button
                className="btn btn-sm btn-ghost icon-btn"
                onClick={() => listen(options.bleep_sound ?? "classic")}
                aria-label={t("edit.bleep_listen")}
                title={t("edit.bleep_listen")}
                disabled={options.bleep_sound === "custom" && !custom}
              >
                <Icon name="play" />
              </button>
              {options.bleep_sound === "custom" && (
                <>
                  <button className="btn btn-sm btn-ghost" onClick={() => file.current?.click()}>
                    <Icon name="upload" />
                    {custom ? t("edit.bleep_replace") : t("edit.bleep_upload")}
                  </button>
                  <input
                    ref={file}
                    type="file"
                    accept="audio/*"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (!f) return;
                      api
                        .uploadBleep(f)
                        .then((b) => {
                          setCustom(b.custom);
                          setRev((r) => r + 1);
                        })
                        .catch(() => setCustom(false));
                    }}
                  />
                </>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="render-row">
        <label>{t("edit.cuts")}</label>
        <div className="edit-cell">
          <Segmented<CutLevel>
            value={options.cuts}
            options={CUTS.map((m) => ({ value: m, label: t(`edit.cuts.${m}`) }))}
            onChange={(m) => setOption({ cuts: m })}
            label={t("edit.cuts")}
          />
          {hasClip && plan && options.cuts !== "off" && (
            <span className="edit-note">
              {autoCut > 0.05 ? t("edit.cut_seconds", { s: num(Math.round(autoCut * 10) / 10) }) : t("edit.cut_none")}
            </span>
          )}
        </div>
      </div>
      <div className="render-row">
        <label>{t("edit.zoom")}</label>
        <div className="edit-cell">
          <Segmented<ZoomLevel>
            value={options.zoom}
            options={ZOOMS.map((m) => ({ value: m, label: t(`edit.zoom.${m}`) }))}
            onChange={(m) => setOption({ zoom: m })}
            label={t("edit.zoom")}
          />
          {hasClip && plan && options.zoom !== "off" && <span className="edit-note">{t("edit.zoom_n", { n: pulses })}</span>}
        </div>
      </div>
      <div className="render-row">
        <label>{t("edit.music")}</label>
        <div className="edit-cell">
          <div className="edit-line">
            <Toggle checked={options.music} onChange={(v) => setOption({ music: v })} label={t("edit.music")} />
            {options.music && analyzed.length > 0 && hasClip && (
              <select
                className="select select-sm"
                value={musicChoice === undefined ? "__auto" : musicChoice === "" ? "__none" : musicChoice}
                onChange={(e) => {
                  const v = e.target.value;
                  setMusicChoice(v === "__auto" ? null : v === "__none" ? "" : v);
                }}
                aria-label={t("edit.music_song")}
              >
                <option value="__auto">
                  {sugg ? t("edit.music_ai", { title: sugg.title, mood: t(`mood.${sugg.mood}`) }) : t("edit.music_ai_short")}
                </option>
                {analyzed.map((x) => (
                  <option key={x.name} value={x.name}>
                    {x.title}
                    {x.moods.length ? ` · ${x.moods.map((m) => t(`mood.${m}`)).join(", ")}` : ""}
                  </option>
                ))}
                <option value="__none">{t("edit.music_none")}</option>
              </select>
            )}
          </div>
          {options.music && analyzed.length === 0 && (
            <a className="edit-note link" href={href.studio("music")}>
              <Icon name="music" size={12} /> {t("edit.music_empty")}
            </a>
          )}
          {options.music && plan?.music && <span className="edit-note">{t("edit.music_ducking")}</span>}
        </div>
      </div>
      <div className="render-row">
        <label>{t("loop.label")}</label>
        <div className="edit-cell">
          <div className="edit-line">
            <Toggle checked={options.loop} onChange={(v) => setOption({ loop: v })} label={t("loop.label")} />
            {options.loop && hasClip && onLoopPreview && (
              <button className="btn btn-sm btn-ghost" onClick={onLoopPreview} disabled={!seam} title={t("loop.preview_hint")}>
                <Icon name="repeat" size={13} />
                {t("loop.preview")}
              </button>
            )}
          </div>
          {!options.loop && <span className="edit-note">{t("loop.hint")}</span>}
          {options.loop && hasClip && seam && (
            <span className="edit-note" data-testid="loop-seam">
              {moved === 0
                ? t("loop.end_kept")
                : moved > 0
                  ? t("loop.end_later", { s: num(moved, 1) })
                  : t("loop.end_earlier", { s: num(-moved, 1) })}
              {seam.last_word && seam.first_word && ` · “${seam.last_word}” → “${seam.first_word}”`}
              {seam.reasons.filter((r) => r !== "mid_speech").length > 0 &&
                ` · ${seam.reasons.filter((r) => r !== "mid_speech").map((r) => t(`loop.why.${r}`)).join(", ")}`}
              {seam.reasons.includes("mid_speech") && ` · ${t("loop.why.mid_speech")}`}
              {seam.source === "ai" && ` · ${t("loop.ai")}`}
            </span>
          )}
          {options.loop && (options.hook_flash || (options.brand && (plan?.brand_preset?.intro.enabled || plan?.brand_preset?.outro.enabled))) && (
            <span className="edit-note warn-text">{t("loop.no_flash_cards")}</span>
          )}
        </div>
      </div>
      <FunEffects options={options} setOption={setOption} plan={plan} />
      <div className="render-row">
        <label>{t("edit.brand")}</label>
        <div className="edit-cell">
          <div className="edit-line">
            <Toggle checked={options.brand} onChange={(v) => setOption({ brand: v })} label={t("edit.brand")} />
            {preset ? (
              <a className="edit-note link" href={href.studio("brand")}>
                {preset.name}
              </a>
            ) : (
              <a className="edit-note link" href={href.studio("brand")}>
                {t("edit.brand_setup")}
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
