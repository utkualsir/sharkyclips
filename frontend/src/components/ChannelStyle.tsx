import { useEffect, useState } from "react";
import { channelApi, type ChannelStyleEdits, type ChannelStyleView } from "../api";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { CopyButton, ProgressBar, Toggle, Sep } from "./ui";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
const words = (s: string) =>
  s
    .split(/[,\n]/)
    .map((x) => x.trim())
    .filter(Boolean);

/** Studio > Brand kit > Channel style (1.2.51): how the creator writes, learned (read only) from
 * their own YouTube channel; every title / description / hashtag the app writes follows it. */
export function ChannelStyleCard() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick } = useJobs();
  const [v, setV] = useState<ChannelStyleView | null>(null);
  const [e, setE] = useState<ChannelStyleEdits | null>(null);
  const [rules, setRules] = useState("");
  const [avoid, setAvoid] = useState("");
  const [always, setAlways] = useState("");
  const analyzing = jobs.find((j) => j.kind === "channel_style" && isActive(j));
  const previewing = jobs.find((j) => j.kind === "style_preview" && isActive(j));
  const fill = (x: ChannelStyleView) => {
    setV(x);
    setE(x.edits);
    setRules(x.edits.extra_rules.join("\n"));
    setAvoid(x.edits.avoid.join(", "));
    setAlways(x.edits.always_hashtags.join(" "));
  };
  useEffect(() => {
    channelApi.view(lang).then(fill).catch(() => {});
  }, [lang, finishedTick]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!v || !e) return null;
  const err = (x: any) => toast({ kind: "err", text: x.message, hint: x.hint });
  const next: Partial<ChannelStyleEdits> = {
    ...e,
    extra_rules: lines(rules),
    avoid: words(avoid),
    always_hashtags: always.split(/[\s,]+/).filter(Boolean),
  };
  const dirty = JSON.stringify(next) !== JSON.stringify(v.edits);
  const save = async () => {
    try {
      fill(await channelApi.save(next));
      toast({ kind: "ok", text: t("common.saved") });
    } catch (x) {
      err(x);
    }
  };
  const analyze = () => channelApi.analyze().catch(err);
  const preview = () => channelApi.preview().catch(err);
  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(lang, { dateStyle: "medium" }) : "");
  const kindLabel = (k: string) => t(`cstyle.kind_${k}`);
  const fmtLabel = (f: string) => t(f === "short" ? "cstyle.fmt_short" : "cstyle.fmt_long");

  return (
    <section className="card setting" id="channel-style">
      <div>
        <h2>{t("cstyle.title")}</h2>
        <p>{t("cstyle.desc")}</p>
        <p className="field-hint">{t("cstyle.readonly")}</p>
      </div>
      <div style={{ display: "grid", gap: 14, minWidth: 0 }}>
        {!v.connected && (
          <div className="notice notice-warn" role="status">
            <Icon name="alert" />
            <div>{t("cstyle.not_connected")}</div>
          </div>
        )}
        <div className="save-line" style={{ flexWrap: "wrap", gap: 8 }}>
          <span className="muted">
            {v.analyzed_at
              ? t("cstyle.analyzed", {
                  channel: v.channel?.title ?? "",
                  n: v.profile?.counts.total ?? 0,
                  date: when(v.analyzed_at),
                  next: when(v.next_at),
                })
              : t("cstyle.never")}
          </span>
          <button className="btn btn-sm btn-primary" onClick={analyze} disabled={!v.connected || !!analyzing}>
            <Icon name="refresh" />
            {analyzing ? t("cstyle.analyzing") : t("cstyle.reanalyze")}
          </button>
        </div>
        {analyzing && <ProgressBar value={analyzing.progress ?? null} />}

        {v.summary && (
          <>
            <div className="toggle-line">
              <span>{t("cstyle.enabled")}</span>
              <Toggle checked={e.enabled} onChange={(x) => setE({ ...e, enabled: x })} label={t("cstyle.enabled")} />
            </div>

            <div className="cstyle-grid">
              {v.summary.styles.map((s) => (
                <div className="cstyle-box" key={s.key}>
                  <h3>
                    {kindLabel(s.kind)}<Sep />{fmtLabel(s.format)} <span className="muted mono">({s.n})</span>
                  </h3>
                  <span className="field-label">{t("cstyle.titles")}</span>
                  <ul>
                    {s.title.map((x) => (
                      <li key={x} dir="auto">
                        {x}
                      </li>
                    ))}
                  </ul>
                  {s.description.length > 0 && (
                    <>
                      <span className="field-label">{t("cstyle.descriptions")}</span>
                      <ul>
                        {s.description.map((x) => (
                          <li key={x} dir="auto">
                            {x}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {s.patterns.length > 0 && (
                    <>
                      <span className="field-label">{t("cstyle.patterns")}</span>
                      <div className="cstyle-tags" dir="auto">
                        {s.patterns.join(", ")}
                      </div>
                    </>
                  )}
                  {s.fixed_lines.length > 0 && (
                    <details>
                      <summary>{t("cstyle.fixed")}</summary>
                      <pre className="channel-preview" dir="auto">
                        {s.fixed_lines.join("\n")}
                      </pre>
                    </details>
                  )}
                  {s.hashtags.length > 0 && (
                    <div className="cstyle-tags" dir="auto">
                      {s.hashtags.join(" ")}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {v.summary.performance.length > 0 && (
              <div style={{ display: "grid", gap: 8 }}>
                <span className="field-label">{t("cstyle.perf")}</span>
                <div className="cstyle-grid">
                  {v.summary.performance.map((p) => (
                    <div className="cstyle-box" key={p.format}>
                      <h3>
                        {fmtLabel(p.format)}{" "}
                        <span className="muted mono">
                          ({t("cstyle.perf_n", { n: p.n, k: p.k })})
                        </span>
                      </h3>
                      <ul>
                        {p.works.map((w) => (
                          <li key={`w${w.label}`}>
                            ✅ {w.label}: {pct(w.top)} / {pct(w.bottom)}
                          </li>
                        ))}
                        {p.weak.map((w) => (
                          <li key={`k${w.label}`}>
                            ⚠️ {w.label}: {pct(w.top)} / {pct(w.bottom)}
                          </li>
                        ))}
                      </ul>
                      {p.top_words.length > 0 && (
                        <div className="cstyle-tags">
                          {t("cstyle.top_words")}: {p.top_words.join(", ")}
                        </div>
                      )}
                      <details>
                        <summary>{t("cstyle.top_bottom")}</summary>
                        <ul>
                          {p.top.map((x) => (
                            <li key={`t${x.id}`} dir="auto">
                              ▲ {x.title} <span className="muted mono">{x.views}</span>
                            </li>
                          ))}
                          {p.bottom.map((x) => (
                            <li key={`b${x.id}`} dir="auto">
                              ▼ {x.title} <span className="muted mono">{x.views}</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: "grid", gap: 8 }}>
              <div className="save-line" style={{ flexWrap: "wrap", gap: 8 }}>
                <span className="field-label">{t("cstyle.preview")}</span>
                <button className="btn btn-sm" onClick={preview} disabled={!!previewing}>
                  <Icon name="sparkles" />
                  {previewing ? t("cstyle.previewing") : v.preview ? t("cstyle.preview_again") : t("cstyle.preview_make")}
                </button>
              </div>
              <span className="field-hint">{t("cstyle.preview_hint")}</span>
              {v.preview && (
                <div className="cstyle-scroll">
                  <table className="cstyle-compare">
                    <thead>
                      <tr>
                        <th scope="col">{t("cstyle.real")}</th>
                        <th scope="col">{t("cstyle.generated")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.preview.items.map((it) => (
                        <tr key={it.id}>
                          <td dir="auto">
                            {it.real}
                            <div className="muted">
                              {fmtLabel(it.format)}<Sep />{it.views}
                            </div>
                          </td>
                          <td dir="auto">
                            <ol>
                              {it.generated.map((g) => (
                                <li key={g}>{g}</li>
                              ))}
                            </ol>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        <div style={{ display: "grid", gap: 10 }}>
          <span className="field-label">{t("cstyle.edit")}</span>
          <div className="brand-grid">
            {(["short", "long"] as const).map((f) => (
              <label key={f}>
                <span className="field-label">{t("cstyle.case_for", { fmt: fmtLabel(f) })}</span>
                <select
                  className="select"
                  value={e.case[f]}
                  onChange={(x) => setE({ ...e, case: { ...e.case, [f]: x.target.value as ChannelStyleEdits["case"]["short"] } })}
                >
                  <option value="auto">{t("cstyle.case_auto")}</option>
                  <option value="upper">{t("cstyle.case_upper")}</option>
                  <option value="mixed">{t("cstyle.case_mixed")}</option>
                </select>
              </label>
            ))}
          </div>
          <label>
            <span className="field-label">{t("cstyle.always")}</span>
            <input className="input" dir="ltr" value={always} placeholder="#yourchannel" onChange={(x) => setAlways(x.target.value)} />
          </label>
          <label>
            <span className="field-label">{t("cstyle.rules")}</span>
            <textarea className="textarea words-area short" dir="auto" value={rules} onChange={(x) => setRules(x.target.value)} />
            <span className="field-hint">{t("cstyle.rules_hint")}</span>
          </label>
          <label>
            <span className="field-label">{t("cstyle.avoid")}</span>
            <input className="input" dir="auto" value={avoid} onChange={(x) => setAvoid(x.target.value)} />
          </label>
          <label>
            <span className="field-label">{t("cstyle.notes")}</span>
            <textarea className="textarea words-area short" dir="auto" value={e.notes} onChange={(x) => setE({ ...e, notes: x.target.value })} />
          </label>
          {v.summary_md && (
            <details>
              <summary>{t("cstyle.summary")}</summary>
              <div style={{ marginTop: 6 }}>
                <CopyButton text={v.summary_md} />
              </div>
              <pre className="channel-preview cstyle-md" dir="auto">
                {v.summary_md}
              </pre>
              <span className="field-hint">{t("cstyle.files", { file: v.files.profile })}</span>
            </details>
          )}
          <div className="save-line">
            <span className="muted">{t("cstyle.applies")}</span>
            <button className="btn btn-primary btn-sm" disabled={!dirty} onClick={save}>
              {t("common.save")}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
