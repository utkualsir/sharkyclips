import { useEffect, useState } from "react";
import { api, type YoutubeStatus } from "../api";
import { Icon } from "../components/Icons";
import { Toggle } from "../components/ui";
import { ConnectYoutube, YoutubeAccount } from "../components/YoutubeConnect";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { chooseLanguage, useMeta } from "../meta";
import { useTheme } from "../theme";
import { useUiMode } from "../uimode";

/** Easy mode settings: only what a beginner needs. Everything else lives in Pro mode. */
export default function EasySettings() {
  const { t, lang, setLang } = useI18n();
  const meta = useMeta();
  const [theme, , toggleTheme] = useTheme();
  const { settings, update, setMode } = useUiMode();
  const [yt, setYt] = useState<YoutubeStatus | null>(null);

  useEffect(() => {
    api.youtube().then(setYt).catch(() => {});
  }, []);

  return (
    <main className="page ez-page ez-settings">
      <div className="ez-hero">
        <h1 className="display">{t("nav.settings")}</h1>
      </div>

      <section className="card ez-set-card" aria-labelledby="ez-set-yt">
        <h2 id="ez-set-yt">{t("easy.set_youtube")}</h2>
        {yt?.connected ? (
          <YoutubeAccount yt={yt} onStatus={setYt} onDisconnect={() => api.youtubeDisconnect().then(setYt).catch(() => {})} />
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("easy.connect_body")}</p>
            <ConnectYoutube yt={yt} onStatus={setYt} onAdvanced={() => setMode("pro")} />
          </>
        )}
      </section>

      <section className="card ez-set-card" aria-labelledby="ez-set-pub">
        <h2 id="ez-set-pub">{t("easy.set_publishing")}</h2>
        <div className="toggle-line">
          <span>
            <b>{t("easy.set_auto_plan")}</b>
            <span className="muted ez-hint">{t("easy.set_auto_plan_hint")}</span>
          </span>
          <Toggle
            checked={settings?.upload_when === "auto"}
            onChange={(v) => update({ upload_when: v ? "auto" : "now" })}
            label={t("easy.set_auto_plan")}
          />
        </div>
        {meta?.is_local && (
          <div className="toggle-line">
            <span>
              <b>{t("easy.set_open_folder")}</b>
              <span className="muted ez-hint" dir="ltr">
                {settings?.downloads}
              </span>
            </span>
            <Toggle checked={settings?.open_folder !== false} onChange={(v) => update({ open_folder: v })} label={t("easy.set_open_folder")} />
          </div>
        )}
      </section>

      <section className="card ez-set-card" aria-labelledby="ez-set-look">
        <h2 id="ez-set-look">{t("easy.set_look")}</h2>
        <label className="field">
          <span className="field-label">{t("lang.label")}</span>
          <select className="select" value={lang} onChange={(e) => chooseLanguage(e.target.value, setLang)}>
            {UI_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <div className="toggle-line">
          <span>
            <b>{t("theme.dark")}</b>
          </span>
          <Toggle checked={theme === "dark"} onChange={toggleTheme} label={t("theme.dark")} />
        </div>
        <button className="link-btn" onClick={() => update({ tour_done: false }).then(() => (window.location.hash = "#/"))}>
          <Icon name="sparkles" size={14} /> {t("easy.set_tour_again")}
        </button>
      </section>

      <section className="card ez-set-card ez-set-pro">
        <div>
          <h2>{t("easy.pro_mode")}</h2>
          <p className="muted" style={{ margin: 0 }}>{t("easy.set_pro_body")}</p>
        </div>
        <button className="btn btn-lg" onClick={() => setMode("pro")}>
          {t("easy.switch_to_pro")}
        </button>
      </section>
    </main>
  );
}
