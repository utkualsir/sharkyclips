import { useCallback, useEffect, useState } from "react";
import { ApiError, liveApi, phoneApi, type PhoneStatus } from "../api";
import { PhoneConnect } from "../components/Phone";
import { AboutCard } from "../components/Licenses";
import { Icon } from "../components/Icons";
import { href } from "../router";
import { useToast } from "../toast";
import { Toggle } from "../components/ui";
import { AutopilotCard } from "../components/EasyAuto";
import { AccountsGrid } from "../components/Accounts";
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
  const [phone, setPhone] = useState<PhoneStatus | null>(null);
  const [folder, setFolder] = useState<string | null>(null);
  const toast = useToast();
  const onPhone = useCallback((s: PhoneStatus) => setPhone(s), []);

  useEffect(() => {
    liveApi
      .get()
      .then((l) => setFolder(l.watch.folders[0] ?? ""))
      .catch(() => {});
    phoneApi.get().then(setPhone).catch(() => {});
  }, []);

  const setAuto = async (v: boolean) => {
    try {
      await update({ auto_clip: v });
      const l = await liveApi.get();
      if (l.watch.enabled !== v) {
        await update({ auto_clip: l.watch.enabled }); // the switch shows what really happened
        throw new ApiError(t("auto.no_folder"), null, 400);
      }
      if (v) toast({ kind: "ok", text: t("auto.on_toast") });
    } catch (e) {
      if (e instanceof ApiError)
        toast({ kind: "err", text: e.message, hint: e.hint, action: { label: t("easy.switch_to_pro"), run: () => setMode("pro") } });
    }
  };

  return (
    <main className="page ez-page ez-settings">
      <div className="ez-hero">
        <h1 className="display">{t("nav.settings")}</h1>
        <a className="btn btn-ghost" href={href.trash}>
          <Icon name="trash" size={15} /> {t("trash.disk_link")}
        </a>
      </div>

      <section className="card ez-set-card ez-set-accounts" id="accounts" aria-labelledby="ez-set-acc">
        <h2 id="ez-set-acc">{t("acc.title")}</h2>
        <p className="muted" style={{ marginTop: 0 }}>{t("acc.lede")}</p>
        <AccountsGrid />
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

      <AutopilotCard />

      <section className="card ez-set-card" aria-labelledby="ez-set-auto">
        <h2 id="ez-set-auto">{t("easy.set_auto")}</h2>
        <div className="toggle-line">
          <span>
            <b>{t("auto.switch")}</b>
            <span className="muted ez-hint">
              {folder === "" ? t("auto.no_folder") : folder ? t("easy.auto_hint", { dir: folder }) : t("auto.switch_hint")}
            </span>
          </span>
          <Toggle checked={!!settings?.auto_clip} onChange={setAuto} label={t("auto.switch")} />
        </div>
        <span className="muted ez-hint">{t("easy.auto_marker_hint")}</span>
      </section>

      <section className="card ez-set-card" aria-labelledby="ez-set-fx">
        <h2 id="ez-set-fx">{t("easy.set_fx")}</h2>
        <div className="toggle-line">
          <span>
            <b>{t("easy.swear_strict")}</b>
            <span className="muted ez-hint">{t("easy.swear_strict_hint")}</span>
          </span>
          <Toggle
            checked={(settings?.swear_strict ?? "auto") === "auto"}
            onChange={(v) => update({ swear_strict: v ? "auto" : "normal" })}
            label={t("easy.swear_strict")}
          />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("easy2.set_banner")}</b>
            <span className="muted ez-hint">{t("easy2.set_banner_hint")}</span>
          </span>
          <Toggle checked={settings?.banner !== false} onChange={(v) => update({ banner: v })} label={t("easy2.set_banner")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("easy2.set_speedup")}</b>
            <span className="muted ez-hint">{t("easy2.set_speedup_hint")}</span>
          </span>
          <Toggle checked={!!settings?.speedup} onChange={(v) => update({ speedup: v })} label={t("easy2.set_speedup")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("fx.replay")}</b>
            <span className="muted ez-hint">{t("fx.replay_hint")}</span>
          </span>
          <Toggle checked={!!settings?.replay} onChange={(v) => update({ replay: v })} label={t("fx.replay")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("fx.bubbles")}</b>
            <span className="muted ez-hint">{t("fx.bubbles_hint")}</span>
          </span>
          <Toggle checked={!!settings?.bubbles} onChange={(v) => update({ bubbles: v })} label={t("fx.bubbles")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("fx.memes")}</b>
            <span className="muted ez-hint">{t("fx.memes_hint")}</span>
          </span>
          <Toggle checked={(settings?.memes ?? "off") !== "off"} onChange={(v) => update({ memes: v ? "light" : "off" })} label={t("fx.memes")} />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("extras.cards")}</b>
            <span className="muted ez-hint">{t("extras.cards_hint")}</span>
          </span>
          <Toggle
            checked={(settings?.study_cards ?? "auto") === "auto"}
            onChange={(v) => update({ study_cards: v ? "auto" : "off" })}
            label={t("extras.cards")}
          />
        </div>
        <div className="toggle-line">
          <span>
            <b>{t("extras.viz")}</b>
            <span className="muted ez-hint">{t("extras.viz_hint")}</span>
          </span>
          <Toggle
            checked={(settings?.visualizer ?? "auto") === "auto"}
            onChange={(v) => update({ visualizer: v ? "auto" : "off" })}
            label={t("extras.viz")}
          />
        </div>
      </section>

      <section className="card ez-set-card" aria-labelledby="ez-set-phone">
        <h2 id="ez-set-phone">{t("easy.set_phone")}</h2>
        <p className="muted" style={{ marginTop: 0 }}>{t("easy.phone_body")}</p>
        <PhoneConnect status={phone} onStatus={onPhone} compact />
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

      <AboutCard easy />

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
