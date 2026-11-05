// Settings cards of 1.2.18: AI covers, TikTok / Reels, my-voice dubbing, study cards + music visualizer.
import { useEffect, useState } from "react";
import { coversApi, platformsApi, type CoverAiPlan, type PlatformsOverview, type PostPlatform } from "../extras";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { CopyButton, Segmented, Toggle } from "./ui";

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

// ---------------------------------------------------------------- TikTok / Instagram Reels

export function PlatformsCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [o, setO] = useState<PlatformsOverview | null>(null);
  const [redirect, setRedirect] = useState("");
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => platformsApi.overview().then(setO).catch(() => {});
  useEffect(() => {
    load();
    platformsApi.tiktokRedirect().then((r) => setRedirect(r.redirect_uri)).catch(() => {});
    const onFocus = () => load(); // back from the TikTok sign-in tab
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);
  if (!o) return null;
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const block = (p: PostPlatform) => {
    const s = o[p];
    const name = p === "tiktok" ? "TikTok" : "Instagram Reels";
    const apiNote = s.audited ? "platform.mode_api" : p === "tiktok" ? "platform.mode_api_private" : "platform.mode_api_review";
    return (
      <div className="platform-block" key={p}>
        <h3>{name}</h3>
        <p className="field-hint">
          <b>{t(s.mode === "api" ? "platform.now_api" : "platform.now_semi")}</b>{" "}
          {s.mode === "api" ? t(apiNote, { name }) : t("platform.mode_semi", { name })}
        </p>
        {s.connected ? (
          <>
            <p className="muted">
              <Icon name="check" size={13} /> {t("platform.connected_as", { name: s.account ?? "?" })}
            </p>
            <div className="toggle-line">
              <span>{t("platform.auto_post")}</span>
              <Toggle
                checked={s.mode === "api"}
                onChange={(v) => run(() => platformsApi.setMode(p, v ? "api" : "semi"))}
                label={t("platform.auto_post")}
              />
            </div>
            <label className="check-line">
              <input type="checkbox" checked={!!s.audited} onChange={(e) => run(() => platformsApi.setAudited(p, e.target.checked))} />
              <span>{t(p === "tiktok" ? "platform.audited_tiktok" : "platform.audited_reels")}</span>
            </label>
            <div>
              <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => run(() => platformsApi.forget(p))}>
                {t("platform.disconnect")}
              </button>
            </div>
          </>
        ) : (
          <details className="platform-guide">
            <summary>{t("platform.setup")}</summary>
            {p === "tiktok" ? (
              <ol>
                <li>{t("platform.tt_step1")}</li>
                <li>{t("platform.tt_step2")}</li>
                <li>
                  {t("platform.tt_step3")}
                  <span className="sugg">
                    <span className="mono" dir="ltr">
                      {redirect}
                    </span>
                    <CopyButton text={redirect} />
                  </span>
                </li>
                <li>
                  {t("platform.tt_step4")}
                  <span className="inline-row">
                    <input className="input" aria-label="Client key" placeholder="Client key" value={key} onChange={(e) => setKey(e.target.value)} />
                    <input
                      className="input"
                      type="password"
                      aria-label="Client secret"
                      placeholder="Client secret"
                      value={secret}
                      onChange={(e) => setSecret(e.target.value)}
                    />
                  </span>
                  <span>
                    <button
                      className="btn btn-sm btn-primary"
                      disabled={busy || !key.trim() || !secret.trim()}
                      onClick={() =>
                        run(async () => {
                          const r = await platformsApi.tiktokConnect(key, secret);
                          window.open(r.url, "_blank", "noopener");
                        })
                      }
                    >
                      {t("platform.connect", { name: "TikTok" })}
                    </button>
                  </span>
                </li>
              </ol>
            ) : (
              <ol>
                <li>{t("platform.ig_step1")}</li>
                <li>{t("platform.ig_step2")}</li>
                <li>{t("platform.ig_step3")}</li>
                <li>
                  {t("platform.ig_step4")}
                  <span className="inline-row">
                    <input
                      className="input"
                      type="password"
                      aria-label={t("platform.ig_token")}
                      placeholder={t("platform.ig_token")}
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                    />
                    <button className="btn btn-sm btn-primary" disabled={busy || token.trim().length < 20} onClick={() => run(() => platformsApi.reelsConnect(token))}>
                      {t("platform.connect", { name: "Instagram" })}
                    </button>
                  </span>
                </li>
              </ol>
            )}
            <p className="field-hint">{t("platform.review_note")}</p>
          </details>
        )}
      </div>
    );
  };
  return (
    <section className="card setting" id="platforms">
      <div>
        <h2>{t("platform.settings")}</h2>
        <p>{t("platform.settings_hint")}</p>
      </div>
      <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
        {block("tiktok")}
        {block("reels")}
      </div>
    </section>
  );
}
