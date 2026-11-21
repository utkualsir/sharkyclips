import { useEffect, useState } from "react";
import {
  api,
  type EpisodeState,
  type MyTemplate,
  type MyTemplateState,
} from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Toggle } from "./ui";

const words = (text: string) =>
  text
    .split(/[,\n]/)
    .map((x) => x.trim())
    .filter(Boolean);
const lines = (text: string) =>
  text
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

/** 1.2.63 Settings > My style: the template switch, the social block (posted word for word),
 *  the channel hashtag, typical title words and the episode counters of story games. */
export function MyTemplateCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [st, setSt] = useState<MyTemplateState | null>(null);
  const [d, setD] = useState<MyTemplate | null>(null);
  const [wordsText, setWordsText] = useState("");
  const [examples, setExamples] = useState("");
  const fill = (x: MyTemplateState) => {
    setSt(x);
    setD(x.template);
    setWordsText(x.template.title_words.join(", "));
    setExamples(x.template.title_examples.join("\n"));
  };
  useEffect(() => {
    api
      .myTemplate()
      .then(fill)
      .catch(() => {});
  }, []);
  if (!st || !d) return null;
  const draft: MyTemplate = {
    ...d,
    title_words: words(wordsText),
    title_examples: lines(examples),
  };
  const dirty = JSON.stringify(draft) !== JSON.stringify(st.template);
  const save = async (patch: Partial<MyTemplate>) => {
    try {
      fill(await api.saveMyTemplate(patch));
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const s = st.strings;
  const series = Object.entries(d.series);
  return (
    <section className="card setting" id="my-style">
      <div>
        <h2>{t("mytpl.title")}</h2>
        <p>{t("mytpl.desc")}</p>
        <p className="field-hint">{t("mytpl.private")}</p>
      </div>
      <div
        style={{ display: "grid", gap: 14, alignContent: "start", minWidth: 0 }}
      >
        <div className="toggle-line">
          <Toggle
            checked={d.enabled}
            onChange={(v) => save({ enabled: v })}
            label={t("mytpl.enabled")}
          />
          <span>{t("mytpl.enabled")}</span>
        </div>
        <div className="mytpl-shape" aria-label={t("mytpl.shape")}>
          <div className="field-label">{t("mytpl.shape")}</div>
          <ol
            className="field-hint"
            style={{
              margin: "4px 0 0",
              paddingInlineStart: 18,
              display: "grid",
              gap: 2,
            }}
          >
            <li>
              {t("mytpl.shape.titles", {
                n: st.limits.options,
                max: st.limits.title,
              })}
            </li>
            <li dir="auto">
              {t("mytpl.shape.desc")} <q dir="auto">{s.intro} …</q>{" "}
              <q dir="auto">… {s.outro}</q>
            </li>
            <li dir="auto">{s.cta}</li>
            <li>{t("mytpl.shape.block")}</li>
            <li dir="auto">
              {s.label}{" "}
              {t("mytpl.shape.tags", {
                lo: st.limits.hashtags[0],
                hi: st.limits.hashtags[1],
              })}
            </li>
          </ol>
        </div>
        <label className="field">
          <span className="field-label">{t("mytpl.block")}</span>
          <textarea
            className="textarea mono"
            dir="auto"
            rows={6}
            value={d.social_block}
            placeholder={"🎮 …\n🟩 Kick: https://kick.com/…"}
            onChange={(e) => setD({ ...d, social_block: e.target.value })}
          />
          <span className="field-hint">{t("mytpl.block_hint")}</span>
        </label>
        <div className="toggle-line">
          <Toggle
            checked={d.shorts_socials}
            onChange={(v) => setD({ ...d, shorts_socials: v })}
            label={t("mytpl.shorts_socials")}
          />
          <span>{t("mytpl.shorts_socials")}</span>
        </div>
        <label className="field" style={{ maxWidth: 280 }}>
          <span className="field-label">{t("mytpl.channel_tag")}</span>
          <input
            className="input"
            dir="ltr"
            value={d.channel_tag}
            placeholder="#MyChannel"
            onChange={(e) => setD({ ...d, channel_tag: e.target.value })}
          />
        </label>
        <details className="advanced">
          <summary>{t("adv.more")}</summary>
          <div style={{ display: "grid", gap: 14, marginTop: 10 }}>
            <label className="field">
              <span className="field-label">{t("mytpl.words")}</span>
              <input
                className="input"
                dir="auto"
                value={wordsText}
                onChange={(e) => setWordsText(e.target.value)}
              />
              <span className="field-hint">{t("mytpl.words_hint")}</span>
            </label>
            <label className="field">
              <span className="field-label">{t("mytpl.examples")}</span>
              <textarea
                className="textarea"
                dir="auto"
                rows={4}
                value={examples}
                onChange={(e) => setExamples(e.target.value)}
              />
              <span className="field-hint">{t("mytpl.examples_hint")}</span>
            </label>
            {series.length > 0 && (
              <div>
                <div className="field-label">{t("mytpl.series")}</div>
                <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                  {series.map(([k, v]) => (
                    <label key={k} className="toggle-line" style={{ gap: 10 }}>
                      <span style={{ minWidth: 140 }}>
                        {st.games.find((g) => g.id === k)?.name ??
                          k.replace(/_/g, " ")}
                      </span>
                      <input
                        className="input"
                        type="number"
                        min={1}
                        style={{ width: 96 }}
                        aria-label={t("mytpl.next_episode", { name: k })}
                        value={v.next}
                        onChange={(e) =>
                          setD({
                            ...d,
                            series: {
                              ...d.series,
                              [k]: {
                                next: Math.max(1, Number(e.target.value) || 1),
                              },
                            },
                          })
                        }
                      />
                      <span className="field-hint">{t("mytpl.next_hint")}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </details>
        <div className="save-line">
          <span className="muted">{t("mytpl.applies")}</span>
          <button
            className="btn btn-primary btn-sm"
            disabled={!dirty}
            onClick={() => save(draft)}
          >
            {t("common.save")}
          </button>
        </div>
      </div>
    </section>
  );
}

/** The episode number of a story-game project (BÖLÜM N), editable; hidden for other games. */
export function EpisodeBox({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const [ep, setEp] = useState<EpisodeState | null>(null);
  const [n, setN] = useState("");
  useEffect(() => {
    api
      .episode(projectId)
      .then((x) => {
        setEp(x);
        setN(x.episode ? String(x.episode.n) : "");
      })
      .catch(() => {});
  }, [projectId]);
  if (!ep || !ep.story || !ep.enabled) return null;
  const save = async () => {
    try {
      const x = await api.setEpisode(projectId, n ? Number(n) : null);
      setEp(x);
      toast({ kind: "ok", text: t("mytpl.episode_saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <div className="pub-block episode-box">
      <label className="toggle-line" style={{ gap: 10, flexWrap: "wrap" }}>
        <span className="field-label">{t("mytpl.episode")}</span>
        <input
          className="input"
          type="number"
          min={1}
          style={{ width: 90 }}
          value={n}
          placeholder={t("mytpl.episode_auto")}
          onChange={(e) => setN(e.target.value)}
        />
        <button
          className="btn btn-sm"
          type="button"
          disabled={(ep.episode ? String(ep.episode.n) : "") === n}
          onClick={save}
        >
          {t("common.save")}
        </button>
        <span className="field-hint">
          {t("mytpl.episode_hint", { game: ep.game })}
        </span>
      </label>
    </div>
  );
}
