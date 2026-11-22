import { useEffect, useState } from "react";
import { api, type GameChoice, type GameView } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Sep } from "./ui";

/** 1.2.53: one-tap game picker for Easy mode (auto-detected game + a "beta" badge for new profiles). */
export function GameChip({ pid, disabled, onChanged }: { pid: string; disabled?: boolean; onChanged?: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [view, setView] = useState<GameView | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api.game(pid).then((v) => live && setView(v)).catch(() => {});
    return () => {
      live = false;
    };
  }, [pid]);
  if (!view?.profiles) return null;
  const profiles = Object.values(view.profiles).sort((a, b) => a.name.localeCompare(b.name));
  const cur = view.game ? view.profiles[view.game] : undefined;
  const hint = !cur ? "" : cur.status === "preview" ? t("game.preview_hint")
    : cur.checked?.length ? `${t("game.beta_hint")} ${t("game.checked_hint", { events: cur.checked.join(", ") })}` : t("game.beta_hint");
  const pick = async (choice: GameChoice) => {
    setBusy(true);
    try {
      const r = await api.setGame(pid, choice);
      setView({ ...view, ...r.game });
      onChanged?.();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="game-chip">
      <label className="sr-only" htmlFor={`game-${pid}`}>
        {t("game.pick")}
      </label>
      <select
        id={`game-${pid}`}
        className="select select-sm"
        style={{ width: "auto" }}
        value={view.choice}
        disabled={disabled || busy}
        onChange={(e) => pick(e.target.value as GameChoice)}
      >
        <option value="auto">
          {view.choice === "auto" && cur ? t("game.detected", { game: cur.name }) : t("game.pick_auto")}
        </option>
        {profiles.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
            {p.beta ? ` (${t("game.beta")})` : ""}
          </option>
        ))}
        <option value="other">{t("game.pick_another")}</option>
      </select>
      {cur?.beta && (
        <span className="chip chip-beta" title={hint}>
          {t("game.beta")}
          <span className="sr-only"><Sep />{hint}</span>
        </span>
      )}
    </span>
  );
}
