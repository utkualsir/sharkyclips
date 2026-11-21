import { useI18n } from "../i18n";
import { useUiMode } from "../uimode";
import { openMiniGame } from "./GameDock";
import { Toggle } from "./ui";

/** 1.2.59: Settings line for the waiting mini game (Easy and Pro): on / off and "Play now". */
export function MiniGameSetting() {
  const { t } = useI18n();
  const { settings, update } = useUiMode();
  const on = settings?.minigame !== false;
  return (
    <div className="toggle-line mg-setting" id="minigame">
      <span>
        <b>{t("mg.settings_label")}</b>
        <span className="muted ez-hint">{t("mg.settings_hint")}</span>
        {on && (
          <button type="button" className="link-btn" onClick={openMiniGame}>
            {t("mg.settings_play")}
          </button>
        )}
      </span>
      <Toggle checked={on} onChange={(v) => update({ minigame: v })} label={t("mg.settings_label")} />
    </div>
  );
}
