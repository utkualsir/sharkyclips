// Settings cards of 1.2.18: AI covers, TikTok / Reels, my-voice dubbing, study cards + music visualizer.
import { useEffect, useState } from "react";
import { coversApi, type CoverAiPlan } from "../extras";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Segmented } from "./ui";

export function CoverAiCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [plan, setPlan] = useState<CoverAiPlan | null>(null);
  useEffect(() => {
    coversApi.plan().then(setPlan).catch(() => {});
  }, []);
  if (!plan) return null;
  const run = async (fn: () => Promise<CoverAiPlan>, ok?: (p: any) => string) => {
    try {
      const p = await fn();
      setPlan(p);
      if (ok) toast({ kind: "ok", text: ok(p) });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <section className="card setting" id="cover-ai">
      <div>
        <h2>{t("cover_ai.settings")}</h2>
        <p>{t("cover_ai.settings_hint")}</p>
      </div>
      <div style={{ display: "grid", gap: 12, alignContent: "start" }}>
        <label className="field">
          <span className="field-label">{t("cover_ai.device")}</span>
          <Segmented
            value={plan.device}
            label={t("cover_ai.device")}
            options={(["auto", "gpu", "cpu"] as const).map((d) => ({ value: d, label: t(`cover_ai.device.${d}`) }))}
            onChange={(d) => run(() => coversApi.setDevice(d))}
          />
        </label>
        <p className="field-hint">
          {plan.use === "fallback" ? (
            <>
              <Icon name="camera" size={12} /> {t(`cover_ai.fallback.${plan.capability.reason}`)} {t("cover_ai.fallback_face")}
            </>
          ) : (
            <>
              <Icon name="sparkles" size={12} /> {t(plan.use === "gpu" ? "cover_ai.on_gpu" : "cover_ai.on_cpu", { m: String(plan.minutes_per_picture ?? 0) })}
            </>
          )}
        </p>
        <div className="save-line">
          <span className="muted">
            {plan.model_ready
              ? t("cover_ai.model_ready", { size: fmtBytes(plan.download_bytes) })
              : t("cover_ai.model_missing", { size: fmtBytes(plan.download_bytes) })}
          </span>
          {plan.model_ready && (
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => run(() => coversApi.removeModel(), (p) => t("cover_ai.removed", { size: fmtBytes(p.freed_bytes) }))}
            >
              <Icon name="trash" /> {t("cover_ai.remove")}
            </button>
          )}
        </div>
        <details className="field-hint">
          <summary>{t("cover_ai.licenses")}</summary>
          <ul>
            {plan.licenses.map((l) => (
              <li key={l.name}>
                {l.name} · {l.by} · {l.license}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}
