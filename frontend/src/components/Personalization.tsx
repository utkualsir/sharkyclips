// 1.2.69 Settings > Personalization (Easy and Pro): mode, look (preset), accent colour, detailed
// colours, the readability check, a live preview, reset, theme files. Every change applies to the
// whole app at once (that is the live preview); the preview card shows all the colours together.
import { useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import {
  accentPalette,
  COLOR_KEYS,
  currentColor,
  downloadTheme,
  presetSwatches,
  PRESETS,
  readThemeFile,
  resetPersonal,
  setColor,
  setPersonal,
  usePersonal,
  type ColorKey,
  type ModeSetting,
  type PresetId,
  type Problem,
} from "../personalize";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Segmented, Toggle } from "./ui";

const GROUPS: { key: string; items: ColorKey[] }[] = [
  { key: "pz.g.base", items: ["bg", "surface", "border"] },
  { key: "pz.g.text", items: ["text", "muted", "link"] },
  { key: "pz.g.action", items: ["button", "success", "warn", "danger"] },
  { key: "pz.g.video", items: ["bleep", "caption"] },
];

export function Personalization({ easy }: { easy?: boolean }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { p, problems, mode } = usePersonal();
  const file = useRef<HTMLInputElement>(null);
  const [tick, setTick] = useState(0); // re-read the current colours after a change
  // swatches of the four looks in the current mode (read from themes.css)
  const swatches = useMemo(() => Object.fromEntries(PRESETS.map((id) => [id, presetSwatches(id, mode)])), [mode]);
  const palette = useMemo(() => accentPalette(), []);
  const now = useMemo(() => {
    void tick;
    return Object.fromEntries(COLOR_KEYS.map((k) => [k, currentColor(k)])) as Record<ColorKey, string>;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p, mode, tick]);
  const own = p.colors[mode] ?? {};
  // one line per setting (text on the page, on panels, on chips... is one "Text" line): the worst one
  const list = Object.values(
    problems[mode].reduce<Record<string, Problem>>((acc, x) => {
      const cur = acc[x.what];
      if (!cur || x.ratio < cur.ratio) acc[x.what] = { ...x, fixed: cur && cur.fixed != null && x.fixed != null ? Math.min(cur.fixed, x.fixed) : x.fixed };
      return acc;
    }, {}),
  );
  const ratio = (n: number) => n.toLocaleString(`${lang}-u-nu-latn`, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const whatName = (w: Problem["what"]) => (w === "accent" ? t("pz.accent") : t(`pz.c.${w}`));

  const pickColor = (k: ColorKey, v: string | null) => {
    setColor(mode, k, v);
    setTick((x) => x + 1);
  };

  return (
    <section className={`card pz${easy ? " ez-set-card" : ""}`} id="personalization" aria-labelledby="pz-title">
      <div className="pz-head">
        <h2 id="pz-title">{t("pz.title")}</h2>
        <p className="muted">{t("pz.desc")}</p>
      </div>

      <div className="pz-body">
        <div className="pz-controls">
          {/* mode */}
          <div className="pz-block">
            <div className="field-label" id="pz-mode">{t("pz.mode")}</div>
            <Segmented<ModeSetting>
              label={t("pz.mode")}
              value={p.mode}
              options={(["light", "dark", "system"] as ModeSetting[]).map((m) => ({ value: m, label: t(`pz.mode.${m}`) }))}
              onChange={(m) => setPersonal({ mode: m })}
            />
            <div className="field-hint">{t("pz.mode_hint")}</div>
          </div>

          {/* look */}
          <fieldset className="pz-block pz-fieldset">
            <legend className="field-label">{t("pz.presets")}</legend>
            <div className="pz-presets" role="radiogroup" aria-label={t("pz.presets")}>
              {PRESETS.map((id: PresetId) => {
                const s = swatches[id];
                return (
                  <button
                    key={id}
                    type="button"
                    role="radio"
                    aria-checked={p.preset === id}
                    className={`pz-preset${p.preset === id ? " on" : ""}`}
                    onClick={() => setPersonal({ preset: id, accent: null, colors: { dark: {}, light: {} } })}
                  >
                    <span className="pz-preset-art" aria-hidden="true" style={{ background: s.bg }}>
                      <span className="pz-preset-card" style={{ background: s.surface }}>
                        <span className="pz-preset-line" style={{ background: s.text }} />
                        <span className="pz-preset-line short" style={{ background: s.muted }} />
                        <span className="pz-preset-btn" style={{ background: s.button }} />
                        <span className="pz-preset-dot" style={{ background: s.accent }} />
                      </span>
                    </span>
                    <span className="pz-preset-name">
                      {p.preset === id && <Icon name="check" size={14} />}
                      {t(`pz.preset.${id}`)}
                    </span>
                    <span className="pz-preset-desc muted">{t(`pz.preset.${id}_desc`)}</span>
                  </button>
                );
              })}
            </div>
            <div className="field-hint">{t("pz.preset_hint")}</div>
          </fieldset>

          {/* accent */}
          <fieldset className="pz-block pz-fieldset">
            <legend className="field-label">{t("pz.accent")}</legend>
            <div className="pz-accents" role="radiogroup" aria-label={t("pz.accent")}>
              <button
                type="button"
                role="radio"
                aria-checked={!p.accent}
                className={`pz-swatch pz-swatch-auto${!p.accent ? " on" : ""}`}
                title={t("pz.accent_auto")}
                aria-label={t("pz.accent_auto")}
                onClick={() => setPersonal({ accent: null })}
              >
                <span style={{ background: swatches[p.preset].accent }} />
              </button>
              {palette.map((c) => (
                <button
                  key={c}
                  type="button"
                  role="radio"
                  aria-checked={p.accent === c}
                  className={`pz-swatch${p.accent === c ? " on" : ""}`}
                  aria-label={t("pz.accent_color", { color: c })}
                  title={c}
                  onClick={() => setPersonal({ accent: c })}
                >
                  <span style={{ background: c }} />
                </button>
              ))}
              <label className={`pz-swatch pz-swatch-pick${p.accent && !palette.includes(p.accent) ? " on" : ""}`} title={t("pz.accent_custom")}>
                <span className="visually-hidden">{t("pz.accent_custom")}</span>
                <input
                  type="color"
                  value={p.accent ?? swatches[p.preset].accent.slice(0, 7)}
                  onChange={(e) => setPersonal({ accent: e.target.value })}
                />
                <Icon name="plus" size={14} />
              </label>
            </div>
            <div className="field-hint">{t("pz.accent_hint")}</div>
            <div className="toggle-line">
              <span>
                <b>{t("pz.titlebar")}</b>
                <span className="field-hint">{t("pz.titlebar_hint")}</span>
              </span>
              <Toggle checked={p.titlebar} onChange={(v) => setPersonal({ titlebar: v })} label={t("pz.titlebar")} disabled={!p.accent} />
            </div>
          </fieldset>

          {/* detailed colours */}
          <details className="pz-block pz-details">
            <summary>
              <Icon name="layers" size={16} /> {t("pz.details")}
            </summary>
            <p className="field-hint">{t("pz.details_hint", { mode: t(`pz.mode.${mode}`) })}</p>
            {GROUPS.map((g) => (
              <div key={g.key} className="pz-group">
                <div className="pz-group-title">{t(g.key)}</div>
                <div className="pz-colors">
                  {g.items.map((k) => (
                    <div key={k} className={`pz-color${own[k] ? " own" : ""}`}>
                      <label className="pz-color-pick">
                        <input type="color" value={own[k] ?? now[k]} onChange={(e) => pickColor(k, e.target.value)} />
                        <span>{t(`pz.c.${k}`)}</span>
                      </label>
                      <span className="mono muted pz-color-hex">{(own[k] ?? now[k]).toUpperCase()}</span>
                      {own[k] ? (
                        <button type="button" className="icon-btn" title={t("pz.c_reset")} aria-label={`${t("pz.c_reset")}: ${t(`pz.c.${k}`)}`} onClick={() => pickColor(k, null)}>
                          <Icon name="refresh" size={14} />
                        </button>
                      ) : (
                        <span className="pz-color-gap" aria-hidden="true" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </details>

          {/* readability */}
          <div className="pz-block">
            <div className="toggle-line">
              <span>
                <b>{t("pz.autofix")}</b>
                <span className="field-hint">{t("pz.autofix_hint")}</span>
              </span>
              <Toggle checked={p.autofix} onChange={(v) => setPersonal({ autofix: v })} label={t("pz.autofix")} />
            </div>
            {list.length === 0 ? (
              <p className="pz-ok" role="status">
                <Icon name="check" size={16} /> {t("pz.all_good")}
              </p>
            ) : (
              <div className={`notice ${list.some((x) => x.fixed == null) ? "notice-warn" : ""}`} role="status">
                <Icon name="alert" />
                <div>
                  <div className="notice-title">{t("pz.problems_title")}</div>
                  <ul className="pz-problems">
                    {list.map((x) => (
                      <li key={x.token}>
                        {x.fixed != null
                          ? t("pz.problem_fixed", { what: whatName(x.what), ratio: ratio(x.ratio), fixed: ratio(x.fixed) })
                          : t("pz.problem", { what: whatName(x.what), ratio: ratio(x.ratio), need: ratio(x.need) })}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>

          <div className="pz-actions">
            <button
              type="button"
              className="btn"
              onClick={() => {
                resetPersonal();
                setTick((x) => x + 1);
                toast({ kind: "ok", text: t("pz.reset_done") });
              }}
            >
              <Icon name="refresh" /> {t("pz.reset")}
            </button>
            <button type="button" className="btn" onClick={() => downloadTheme(p)}>
              <Icon name="download" /> {t("pz.export")}
            </button>
            <button type="button" className="btn" onClick={() => file.current?.click()}>
              <Icon name="upload" /> {t("pz.import")}
            </button>
            <input
              ref={file}
              type="file"
              accept=".json,application/json"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f || f.size > 64 * 1024) {
                  if (f) toast({ kind: "err", text: t("pz.import_bad") });
                  return;
                }
                f.text()
                  .then((text) => {
                    const th = readThemeFile(text);
                    if (!th) throw new Error("bad");
                    setPersonal(th);
                    setTick((x) => x + 1);
                    toast({ kind: "ok", text: t("pz.import_done") });
                  })
                  .catch(() => toast({ kind: "err", text: t("pz.import_bad") }));
              }}
            />
          </div>
        </div>

        {/* the preview: the real tokens, so it shows exactly what the app does */}
        <div className="pz-preview" aria-label={t("pz.preview")} role="group">
          <div className="pz-pv-title field-label">{t("pz.preview")}</div>
          <div className="pz-pv" aria-hidden="true">
            <div className="pz-pv-bar">
              <span className="pz-pv-mark" />
              <span className="pz-pv-tab on">{t("pz.pv.tab_a")}</span>
              <span className="pz-pv-tab">{t("pz.pv.tab_b")}</span>
            </div>
            <div className="pz-pv-card">
              <div className="pz-pv-h">{t("pz.pv.title")}</div>
              <p className="pz-pv-muted">{t("pz.pv.body")}</p>
              <p className="pz-pv-cap">
                {t("pz.pv.caption_a")} <span className="pz-pv-hl">{t("pz.pv.caption_word")}</span> <span className="pz-pv-bleep">{t("pz.pv.bleep")}</span>
              </p>
              <div className="pz-pv-progress">
                <span>{t("pz.pv.progress")}</span>
                <span className="progress"><span style={{ width: "62%" }} /></span>
              </div>
              <div className="pz-pv-chips">
                <span className="badge pz-pv-ok">{t("pz.pv.ok")}</span>
                <span className="badge pz-pv-warn">{t("pz.pv.warn")}</span>
                <span className="badge pz-pv-err">{t("pz.pv.err")}</span>
                <span className="pz-pv-link">{t("pz.pv.link")}</span>
              </div>
              <div className="pz-pv-btns">
                <span className="btn btn-primary btn-sm">{t("pz.pv.button")}</span>
                <span className="btn btn-sm">{t("pz.pv.button2")}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
