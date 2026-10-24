import { useEffect, useState } from "react";
import { api, type LlmInfo, type Mode, type Settings as SettingsT } from "../api";
import { Icon } from "../components/Icons";
import { CopyButton, Segmented, Toggle } from "../components/ui";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { chooseLanguage, useMeta } from "../meta";
import { useTheme } from "../theme";
import { useToast } from "../toast";

function parseWords(text: string): string[] {
  const out: string[] = [];
  for (const line of text.split(/\n|,/)) {
    const w = line.trim().replace(/\s+/g, " ");
    if (w && !out.includes(w)) out.push(w);
  }
  return out;
}

export default function Settings() {
  const { t, lang, setLang } = useI18n();
  const meta = useMeta();
  const toast = useToast();
  const [theme, setTheme] = useTheme();
  const [settings, setSettings] = useState<SettingsT | null>(null);
  const [trigLang, setTrigLang] = useState(lang);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingTriggers, setSavingTriggers] = useState(false);
  const [llmInfo, setLlmInfo] = useState<LlmInfo | null>(null);
  const [glossary, setGlossary] = useState("");

  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      setDrafts(Object.fromEntries(UI_LANGUAGES.map((l) => [l.code, (s.custom_triggers[l.code] ?? []).join("\n")])));
      setGlossary(s.glossary.join("\n"));
    });
    api.llm().then(setLlmInfo).catch(() => setLlmInfo(null));
  }, []);

  const glossaryDirty = settings && parseWords(glossary).join("\n") !== settings.glossary.join("\n");

  const save = async (patch: Partial<SettingsT>) => {
    try {
      const s = await api.saveSettings(patch);
      setSettings(s);
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const saveTriggers = async () => {
    setSavingTriggers(true);
    const all = Object.fromEntries(Object.entries(drafts).map(([k, v]) => [k, parseWords(v)]));
    await save({ custom_triggers: all });
    setSavingTriggers(false);
  };

  const dirty =
    settings &&
    UI_LANGUAGES.some(
      (l) => parseWords(drafts[l.code] ?? "").join("\n") !== (settings.custom_triggers[l.code] ?? []).join("\n"),
    );

  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1 className="display">{t("settings.title")}</h1>
          <p className="lede">{t("settings.lede")}</p>
        </div>
      </div>

      {!settings ? (
        <div className="settings-list">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card skeleton" style={{ height: 110 }} />
          ))}
        </div>
      ) : (
        <div className="settings-list">
          <section className="card setting">
            <div>
              <h3>{t("lang.label")}</h3>
              <p>{t("settings.ui_language_desc")}</p>
            </div>
            <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
              <select className="select" value={lang} onChange={(e) => chooseLanguage(e.target.value, setLang)}>
                {UI_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
              <div>
                <div className="field-label" style={{ marginBottom: 6 }}>
                  {t("settings.theme")}
                </div>
                <Segmented
                  value={theme}
                  options={[
                    { value: "dark", label: t("theme.dark") },
                    { value: "light", label: t("theme.light") },
                  ]}
                  onChange={setTheme}
                />
                <div className="field-hint" style={{ marginTop: 6 }}>
                  {t("settings.theme_desc")}
                </div>
              </div>
            </div>
          </section>

          <section className="card setting">
            <div>
              <h3>{t("settings.output_language")}</h3>
              <p>{t("settings.output_language_desc")}</p>
            </div>
            <div>
              <select
                className="select"
                value={settings.output_language}
                onChange={(e) => save({ output_language: e.target.value })}
              >
                {UI_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
          </section>

          <section className="card setting" id="ai">
            <div>
              <h3>{t("settings.ai")}</h3>
              <p>{t("settings.ai_desc")}</p>
            </div>
            <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
              <div>
                <label className="field-label" htmlFor="llm-model" style={{ display: "block", marginBottom: 6 }}>
                  {t("settings.llm_model")}
                </label>
                <select
                  id="llm-model"
                  className="select"
                  value={settings.llm_model}
                  disabled={!llmInfo?.server}
                  onChange={(e) => save({ llm_model: e.target.value })}
                >
                  <option value="auto">{t("settings.llm_auto", { model: llmInfo?.auto ?? "…" })}</option>
                  {llmInfo?.installed.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}
                      {m.params ? ` · ${m.params}` : ""}
                      {m.size_gb ? ` · ${m.size_gb} GB` : ""}
                    </option>
                  ))}
                  {settings.llm_model !== "auto" && !llmInfo?.installed.some((m) => m.name === settings.llm_model) && (
                    <option value={settings.llm_model}>{settings.llm_model}</option>
                  )}
                </select>
                {llmInfo && !llmInfo.server && (
                  <div className="field-hint" style={{ marginTop: 6 }}>
                    {t("settings.llm_offline")}
                  </div>
                )}
              </div>
              <div className="toggle-line">
                <Toggle
                  checked={settings.auto_analyze}
                  onChange={(v) => save({ auto_analyze: v })}
                  label={t("settings.auto_analyze")}
                />
                <span>{t("settings.auto_analyze")}</span>
              </div>
              <div>
                <label className="field-label" htmlFor="glossary" style={{ display: "block", marginBottom: 4 }}>
                  {t("settings.glossary")}
                </label>
                <div className="field-hint" style={{ marginBottom: 8 }}>
                  {t("settings.glossary_desc")}
                </div>
                <textarea
                  id="glossary"
                  className="textarea"
                  dir="auto"
                  value={glossary}
                  placeholder={t("settings.glossary_placeholder")}
                  onChange={(e) => setGlossary(e.target.value)}
                />
                <div className="save-line">
                  <span className="muted">{t("settings.glossary_note")}</span>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={!glossaryDirty}
                    onClick={() => save({ glossary: parseWords(glossary) })}
                  >
                    {t("common.save")}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="card setting">
            <div>
              <h3>{t("settings.triggers")}</h3>
              <p>{t("settings.triggers_desc")}</p>
            </div>
            <div>
              <div className="lang-tabs" role="group">
                {UI_LANGUAGES.map((l) => {
                  const n = parseWords(drafts[l.code] ?? "").length;
                  return (
                    <button key={l.code} type="button" aria-pressed={trigLang === l.code} onClick={() => setTrigLang(l.code)}>
                      {l.name}
                      {n > 0 && <span className="n mono">{n}</span>}
                    </button>
                  );
                })}
              </div>
              <textarea
                className="textarea"
                dir={trigLang === "ar" ? "rtl" : "auto"}
                lang={trigLang}
                value={drafts[trigLang] ?? ""}
                placeholder={t("settings.triggers_placeholder")}
                onChange={(e) => setDrafts({ ...drafts, [trigLang]: e.target.value })}
              />
              <div className="save-line">
                <span className="muted">
                  {t("settings.triggers_count", { n: parseWords(drafts[trigLang] ?? "").length })} ·{" "}
                  {t("settings.triggers_note")}
                </span>
                <button className="btn btn-primary btn-sm" disabled={!dirty || savingTriggers} onClick={saveTriggers}>
                  {t("common.save")}
                </button>
              </div>
            </div>
          </section>

          <section className="card setting">
            <div>
              <h3>{t("settings.encoder")}</h3>
              <p>{t("settings.encoder_desc")}</p>
            </div>
            <div>
              <select
                className="select"
                value={settings.video_encoder}
                onChange={(e) => save({ video_encoder: e.target.value })}
              >
                <option value="auto">{t("settings.encoder_auto")}</option>
                {meta?.encoders.map((e) => (
                  <option key={e.name} value={e.name}>
                    {e.label} ({e.name})
                  </option>
                ))}
              </select>
            </div>
          </section>

          <section className="card setting">
            <div>
              <h3>{t("settings.mode")}</h3>
              <p>{t("settings.mode_desc")}</p>
            </div>
            <div>
              <Segmented<Mode>
                block
                value={settings.default_mode}
                options={(["gaming", "study", "music"] as Mode[]).map((m) => ({ value: m, label: t(`mode.${m}`) }))}
                onChange={(m) => save({ default_mode: m })}
              />
            </div>
          </section>

          <section className="card setting">
            <div>
              <h3>{t("settings.lan")}</h3>
              <p>{t("settings.lan_desc")}</p>
            </div>
            <div style={{ alignSelf: "center" }}>
              {meta?.lan_url ? (
                <div style={{ display: "grid", gap: 6 }}>
                  <span className="muted">{t("settings.lan_on")}</span>
                  <div className="sugg">
                    <Icon name="globe" />
                    <span className="mono" dir="ltr">
                      {meta.lan_url}
                    </span>
                    <CopyButton text={meta.lan_url} />
                  </div>
                </div>
              ) : (
                <div className="sugg">
                  <span className="mono" dir="ltr">
                    python cli.py serve --lan
                  </span>
                  <CopyButton text="python cli.py serve --lan" />
                </div>
              )}
            </div>
          </section>

          <p className="muted mono" style={{ textAlign: "center", fontSize: 12 }}>
            {t("settings.version", { v: meta?.version ?? "" })}
          </p>
        </div>
      )}
    </main>
  );
}
