import { useEffect, useState } from "react";
import { api, type LlmInfo, type Mode, type Settings as SettingsT, type UpdateStatus } from "../api";
import { Icon } from "../components/Icons";
import { CopyButton, JobLine, Segmented, Toggle } from "../components/ui";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { chooseLanguage, useMeta } from "../meta";
import { useTheme } from "../theme";
import { useToast } from "../toast";

function SpeedCompare({ info, fast }: { info: LlmInfo; fast: boolean }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs } = useJobs();
  const job = jobs.find((j) => j.kind === "benchmark" && isActive(j));
  const normal = info.speed.normal;
  const quick = info.speed.fast;
  const rows = [
    { key: "normal", label: t("speed.normal"), model: info.normal_model, s: normal?.seconds_per_clip, on: !fast },
    { key: "fast", label: t("speed.fast"), model: info.fast_model, s: quick?.seconds_per_clip, on: fast },
  ];
  const max = Math.max(1, ...rows.map((r) => r.s ?? 0));
  const ratio = normal && quick && quick.seconds_per_clip > 0 ? normal.seconds_per_clip / quick.seconds_per_clip : null;
  const run = () => api.benchmark().catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  return (
    <div className="speed-box">
      <div className="pub-row">
        <span className="field-label">{t("speed.title")}</span>
        {ratio != null && <span className="chip chip-gold">{t("speed.faster", { x: num(ratio, 1) })}</span>}
      </div>
      <ul className="bars">
        {rows.map((r) => (
          <li key={r.key}>
            <div className="bar-top">
              <span>
                {r.label} <span className="muted mono">· {r.model}</span>
                {r.on && <span className="chip chip-outline best-chip">{t("speed.active")}</span>}
              </span>
              <span className="mono">{r.s != null ? t("speed.per_clip", { s: num(r.s, r.s < 10 ? 1 : 0) }) : t("speed.unknown")}</span>
            </div>
            <div className="sig-bar">
              <span style={{ width: `${r.s != null ? Math.max(2, (r.s / max) * 100) : 0}%` }} />
            </div>
          </li>
        ))}
      </ul>
      {job ? (
        <JobLine job={job} onCancel={() => api.cancelJob(job.id)} />
      ) : (
        <div className="save-line" style={{ marginTop: 10 }}>
          <span className="muted">{t("speed.note")}</span>
          <button className="btn btn-sm" onClick={run} disabled={!info.server}>
            <Icon name="clock" />
            {t("speed.run")}
          </button>
        </div>
      )}
    </div>
  );
}

/** Waits until the restarted server answers again, then reloads the page. */
async function reloadWhenBack() {
  await new Promise((r) => setTimeout(r, 1500));
  for (let i = 0; i < 120; i++) {
    try {
      const res = await fetch("/api/meta", { cache: "no-store" });
      if (res.ok) {
        window.location.reload();
        return;
      }
    } catch {
      // still restarting
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
}

function UpdatesCard() {
  const { t } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const { jobs } = useJobs();
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "restarting" | "manual">("idle");
  const job = jobs.find((j) => j.kind === "update" && (j.id === jobId || isActive(j)));

  const check = () => {
    setChecking(true);
    api
      .updateStatus()
      .then(setStatus)
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
      .finally(() => setChecking(false));
  };

  const install = () =>
    api
      .updateApply()
      .then((j) => setJobId(j.id))
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));

  useEffect(() => {
    if (!job || job.id !== jobId || phase !== "idle") return;
    if (job.status === "done") {
      if (status?.can_restart) {
        setPhase("restarting");
        api
          .updateRestart()
          .then((r) => (r.restarting ? reloadWhenBack() : setPhase("manual")))
          .catch(() => reloadWhenBack());
      } else setPhase("manual");
    } else if (job.status === "error") {
      toast({ kind: "err", text: job.error?.message ?? t("update.failed"), hint: job.error?.hint });
      setJobId(null);
    }
  }, [job, jobId, phase, status, t, toast]);

  let body: React.ReactNode = null;
  if (phase === "restarting") body = <span className="status status-running"><span className="dot" />{t("update.restarting")}</span>;
  else if (phase === "manual") body = <p>{t("update.done_manual")}</p>;
  else if (job && isActive(job)) body = <JobLine job={job} />;
  else if (status) {
    if (status.reason === "fetch_failed") body = <p className="muted">{t("update.fetch_failed")}</p>;
    else if (status.reason)
      body = (
        <p className="muted">
          {t("update.no_git")}{" "}
          <a href={status.releases_url} target="_blank" rel="noreferrer">
            {t("update.open_releases")}
          </a>
        </p>
      );
    else if (!status.available) body = <p className="muted">{t("update.current", { v: status.current })}</p>;
    else
      body = (
        <div style={{ display: "grid", gap: 10 }}>
          <div className="pub-row">
            <strong>{t("update.available", { v: status.latest ?? "" })}</strong>
            <span className="chip chip-gold">{t("update.changes", { n: status.behind })}</span>
          </div>
          {status.changes.length > 0 && (
            <ul className="muted" style={{ margin: 0, paddingInlineStart: 18, fontSize: 13 }}>
              {status.changes.slice(0, 6).map((c, i) => (
                <li key={i} dir="ltr">
                  {c}
                </li>
              ))}
            </ul>
          )}
          <div>
            <button className="btn btn-primary btn-sm" onClick={install} disabled={!meta?.is_local}>
              <Icon name="download" />
              {t("update.install")}
            </button>
          </div>
        </div>
      );
  }

  return (
    <section className="card setting" id="updates">
      <div>
        <h3>{t("settings.updates")}</h3>
        <p>{t("settings.updates_desc", { v: meta?.version ?? "" })}</p>
      </div>
      <div style={{ display: "grid", gap: 12, alignContent: "start" }}>
        {body}
        {phase === "idle" && !(job && isActive(job)) && (
          <div>
            <button className="btn btn-sm" onClick={check} disabled={checking}>
              <Icon name="refresh" />
              {checking ? t("update.checking") : t("update.check")}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

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
  const { finishedTick, lastFinished } = useJobs();

  useEffect(() => {
    if (lastFinished?.kind === "benchmark") api.llm().then(setLlmInfo).catch(() => {});
  }, [finishedTick]); // eslint-disable-line react-hooks/exhaustive-deps

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
                {settings.fast_analysis && (
                  <div className="field-hint" style={{ marginTop: 6 }}>
                    {t("settings.fast_overrides", { model: llmInfo?.fast_model ?? "qwen3.5:4b" })}
                  </div>
                )}
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
              <div className="fast-box">
                <div className="toggle-line" style={{ alignItems: "flex-start" }}>
                  <Toggle
                    checked={settings.fast_analysis}
                    onChange={(v) => save({ fast_analysis: v })}
                    label={t("settings.fast")}
                  />
                  <div>
                    <div style={{ fontWeight: 550 }}>{t("settings.fast")}</div>
                    <div className="field-hint">
                      {t("settings.fast_desc", { model: llmInfo?.fast_model ?? "qwen3.5:4b" })}
                      {llmInfo && !llmInfo.fast_installed && llmInfo.server && <> {t("settings.fast_download")}</>}
                    </div>
                  </div>
                </div>
                {llmInfo && <SpeedCompare info={llmInfo} fast={settings.fast_analysis} />}
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

          <UpdatesCard />

          <p className="muted mono" style={{ textAlign: "center", fontSize: 12 }}>
            {t("settings.version", { v: meta?.version ?? "" })}
          </p>
        </div>
      )}
    </main>
  );
}
