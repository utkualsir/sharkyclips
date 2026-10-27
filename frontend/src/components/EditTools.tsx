import type { BrandState, ClipOptions, CutLevel, EditPlanView, MusicTrack, ProfanityMode, ZoomLevel } from "../api";
import { useI18n } from "../i18n";
import { href } from "../router";
import { Icon } from "./Icons";
import { Segmented, Toggle } from "./ui";

const PROFANITY: ProfanityMode[] = ["auto", "bleep", "mute", "off"];
const CUTS: CutLevel[] = ["off", "light", "strong"];
const ZOOMS: ZoomLevel[] = ["off", "subtle", "strong"];

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

/** Render options of the editing tools (swear words, cuts, zoom, music, brand kit). */
export default function EditTools({ options, setOption, plan, tracks, musicChoice, setMusicChoice, brand, hasClip, onLoopPreview }: Props) {
  const { t, num } = useI18n();
  const seam = plan?.loop ?? null;
  const moved = seam ? Math.round((seam.end - seam.orig_end) * 10) / 10 : 0;
  const bleeps = plan ? plan.words.filter((w) => w.bleep && !w.removed).length : 0;
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
