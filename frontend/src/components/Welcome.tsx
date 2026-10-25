import { useCallback, useEffect, useRef, useState } from "react";
import { api, type HardwareCheck, type PerfMode } from "../api";
import { useAppState } from "../appstate";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { chooseLanguage } from "../meta";
import { SharkLogo } from "./Brand";
import { Icon } from "./Icons";

const SPLASH_MS = 1500;
const SPLASH_KEY = "sc-splash-shown";

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function shownThisSession(): boolean {
  try {
    return sessionStorage.getItem(SPLASH_KEY) === "1";
  } catch {
    return false;
  }
}

/** Start-up splash: once per browser tab session, ~1.5 s, click / Esc skips. The app loads
 * underneath, so it never adds waiting time. When the launcher's splash page already played
 * (?splash=done) only its last frame fades out, for a seamless hand-over. */
export function Splash({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const handedOver = useRef(new URLSearchParams(window.location.search).get("splash") === "done");
  const [phase, setPhase] = useState<"skip" | "show" | "out">(() =>
    handedOver.current ? "out" : shownThisSession() ? "skip" : "show",
  );
  const done = useRef(false);

  const finish = useCallback(() => {
    if (done.current) return;
    done.current = true;
    setPhase("out");
    window.setTimeout(onDone, reducedMotion() ? 120 : 320);
  }, [onDone]);

  useEffect(() => {
    try {
      sessionStorage.setItem(SPLASH_KEY, "1");
    } catch {
      /* private mode */
    }
    if (handedOver.current) {
      const url = new URL(window.location.href);
      url.searchParams.delete("splash");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
      done.current = true;
      const id = window.setTimeout(onDone, reducedMotion() ? 120 : 320);
      return () => window.clearTimeout(id);
    }
    if (phase === "skip") {
      onDone();
      return;
    }
    const id = window.setTimeout(finish, SPLASH_MS);
    const key = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "Enter" || e.key === " ") && finish();
    window.addEventListener("keydown", key);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("keydown", key);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (phase === "skip") return null;
  return (
    <div
      className={`splash${phase === "out" ? " splash-out" : ""}${handedOver.current ? " splash-handover" : ""}`}
      onClick={finish}
      role="status"
      aria-live="polite"
      aria-label="SharkyClips"
    >
      <div className="splash-stage">
        <SharkLogo animated={!handedOver.current} className="splash-logo" />
        <div className="splash-name">SharkyClips</div>
        <p className="splash-slogan">{t("brand.slogan")}</p>
      </div>
      <span className="splash-hint">{t("splash.skip")}</span>
    </div>
  );
}

// ---------------------------------------------------------------- onboarding

const TYPES = [
  { id: "gaming", icon: "gamepad" },
  { id: "study", icon: "book" },
  { id: "music", icon: "music" },
] as const;
const MODES: PerfMode[] = ["silent", "balanced", "turbo"];

/** First launch only: UI language, content types, performance mode (+ a quick hardware check). */
export function Onboarding({ onDone }: { onDone: () => void }) {
  const { t, lang, setLang, num } = useI18n();
  const { state, set } = useAppState();
  const [step, setStep] = useState(0);
  const [types, setTypes] = useState<string[]>(state?.content_types?.length ? state.content_types : ["gaming"]);
  const [mode, setMode] = useState<PerfMode>("silent");
  const [hw, setHw] = useState<HardwareCheck | null>(null);
  const [hwFailed, setHwFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    api.hardwareCheck().then(setHw).catch(() => setHwFailed(true));
  }, []);
  useEffect(() => titleRef.current?.focus(), [step]);

  const finish = async (skip: boolean) => {
    setSaving(true);
    try {
      const res = await api.finishOnboarding(skip ? {} : { ui_language: lang, content_types: types, performance_mode: mode });
      set(res);
    } catch {
      /* the onboarding never blocks the app */
    }
    onDone();
  };

  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && !saving && finish(true);
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saving]);

  const toggleType = (id: string) =>
    setTypes((cur) => (cur.includes(id) ? (cur.length > 1 ? cur.filter((x) => x !== id) : cur) : [...cur, id]));

  const steps = [t("onb.step.language"), t("onb.step.content"), t("onb.step.performance")];
  return (
    <div className="welcome" role="dialog" aria-modal="true" aria-labelledby="onb-title">
      <div className="welcome-card">
        <div className="welcome-top">
          <SharkLogo className="welcome-logo" />
          <ol className="welcome-steps" aria-label={t("onb.progress", { i: step + 1, n: 3 })}>
            {steps.map((s, i) => (
              <li key={s} className={i === step ? "on" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
                <span className="welcome-step-dot">{i < step ? <Icon name="check" size={12} /> : num(i + 1)}</span>
                <span className="welcome-step-label">{s}</span>
              </li>
            ))}
          </ol>
          <button className="welcome-skip" onClick={() => finish(true)} disabled={saving}>
            {t("onb.skip")}
          </button>
        </div>

        {step === 0 && (
          <section className="welcome-body">
            <h1 className="welcome-title" id="onb-title" tabIndex={-1} ref={titleRef}>
              {t("onb.lang.title")}
            </h1>
            <p className="welcome-lede">{t("onb.lang.lede")}</p>
            <div className="welcome-grid welcome-grid-lang" role="radiogroup" aria-label={t("lang.label")}>
              {UI_LANGUAGES.map((l) => (
                <button
                  key={l.code}
                  role="radio"
                  aria-checked={lang === l.code}
                  className={`welcome-option${lang === l.code ? " on" : ""}`}
                  onClick={() => chooseLanguage(l.code, setLang)}
                  lang={l.code}
                  dir={l.code === "ar" ? "rtl" : "ltr"}
                >
                  <b>{l.name}</b>
                  {lang === l.code && <Icon name="check" size={16} />}
                </button>
              ))}
            </div>
          </section>
        )}

        {step === 1 && (
          <section className="welcome-body">
            <h1 className="welcome-title" id="onb-title" tabIndex={-1} ref={titleRef}>
              {t("onb.content.title")}
            </h1>
            <p className="welcome-lede">{t("onb.content.lede")}</p>
            <div className="welcome-grid welcome-grid-3" role="group" aria-label={t("onb.step.content")}>
              {TYPES.map((x) => (
                <button
                  key={x.id}
                  role="checkbox"
                  aria-checked={types.includes(x.id)}
                  className={`welcome-option welcome-option-tall${types.includes(x.id) ? " on" : ""}`}
                  onClick={() => toggleType(x.id)}
                >
                  <span className="welcome-option-icon">
                    <Icon name={x.icon} size={22} />
                  </span>
                  <b>{t(`mode.${x.id}`)}</b>
                  <span>{t(`mode.${x.id}_desc`)}</span>
                  <span className="welcome-check" aria-hidden="true">
                    {types.includes(x.id) && <Icon name="check" size={14} />}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {step === 2 && (
          <section className="welcome-body">
            <h1 className="welcome-title" id="onb-title" tabIndex={-1} ref={titleRef}>
              {t("onb.perf.title")}
            </h1>
            <p className="welcome-lede">{t("onb.perf.lede")}</p>
            <div className="welcome-modes" role="radiogroup" aria-label={t("gov.mode_label")}>
              {MODES.map((m) => (
                <button
                  key={m}
                  role="radio"
                  aria-checked={mode === m}
                  className={`welcome-option welcome-mode${mode === m ? " on" : ""}`}
                  onClick={() => setMode(m)}
                >
                  <span className="welcome-radio" aria-hidden="true" />
                  <span className="welcome-mode-text">
                    <b>
                      {t(`gov.mode.${m}`)}
                      {m === "silent" && <span className="welcome-badge">{t("onb.recommended")}</span>}
                    </b>
                    <span>{t(`gov.mode_desc.${m}`)}</span>
                  </span>
                </button>
              ))}
            </div>
            <HardwareSummary hw={hw} failed={hwFailed} />
          </section>
        )}

        <div className="welcome-foot">
          {step > 0 ? (
            <button className="welcome-btn welcome-btn-ghost" onClick={() => setStep(step - 1)} disabled={saving}>
              <Icon name="chevron-left" className="icon flip-rtl" />
              {t("onb.back")}
            </button>
          ) : (
            <span />
          )}
          {step < 2 ? (
            <button className="welcome-btn welcome-btn-primary" onClick={() => setStep(step + 1)}>
              {t("onb.next")}
              <Icon name="chevron-right" className="icon flip-rtl" />
            </button>
          ) : (
            <button className="welcome-btn welcome-btn-primary" onClick={() => finish(false)} disabled={saving}>
              {saving ? <span className="spinner" /> : <Icon name="check" />}
              {t("onb.finish")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function HardwareSummary({ hw, failed }: { hw: HardwareCheck | null; failed: boolean }) {
  const { t, num } = useI18n();
  if (failed) return null;
  const rows: [string, string][] = hw
    ? [
        [t("onb.hw.gpu"), hw.gpu ? `${hw.gpu}${hw.vram_gb ? ` · ${num(hw.vram_gb, 0)} GB` : ""}` : t("onb.hw.no_gpu")],
        [t("onb.hw.cpu"), `${hw.cpu} · ${num(hw.ram_gb)} GB RAM`],
        [t("onb.hw.speech"), `${hw.whisper.model ?? "—"} · ${hw.whisper.device === "cpu" ? "CPU" : "GPU"}`],
        [t("onb.hw.video"), hw.encoder ? hw.encoder.label : "CPU"],
        [t("onb.hw.ai"), hw.llm.available ? hw.llm.model : t("onb.hw.ai_missing")],
      ]
    : [];
  return (
    <div className="welcome-hw" aria-busy={!hw}>
      <div className="welcome-hw-head">
        <b>{t("onb.hw.title")}</b>
        {hw ? (
          <span className={`welcome-verdict v-${hw.verdict}`}>{t(`onb.hw.verdict.${hw.verdict}`)}</span>
        ) : (
          <span className="welcome-verdict">
            <span className="spinner" style={{ width: 12, height: 12 }} />
            {t("onb.hw.checking")}
          </span>
        )}
      </div>
      {hw && (
        <dl>
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
