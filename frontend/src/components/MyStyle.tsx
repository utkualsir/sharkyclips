import { useEffect, useState } from "react";
import { api, type LongMetadata, type StyleExample, type StyleGlossary, type StyleProfile, type StyleState } from "../api";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { CopyButton, Modal, Segmented, Toggle } from "./ui";

function parseCorrections(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const m = line.split(/=>|→|->/);
    if (m.length === 2 && m[0].trim() && m[1].trim()) out[m[0].trim().toLowerCase()] = m[1].trim();
  }
  return out;
}

const listOf = (text: string, sep: RegExp) =>
  text
    .split(sep)
    .map((x) => x.trim())
    .filter(Boolean);

/** Brand kit > My style: the creator's own proven titles / descriptions, the rules they teach, the gamer glossary. */
export function MyStyleCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [st, setSt] = useState<StyleState | null>(null);
  const [p, setP] = useState<StyleProfile | null>(null);
  const [keep, setKeep] = useState("");
  const [corr, setCorr] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const fill = (x: StyleState) => {
    setSt(x);
    setP(x.profile);
    setKeep(x.glossary.keep.join(", "));
    setCorr(
      Object.entries(x.glossary.corrections)
        .map(([a, b]) => `${a} => ${b}`)
        .join("\n"),
    );
  };
  useEffect(() => {
    api.myStyle().then(fill).catch(() => {});
  }, []);
  if (!st || !p) return null;
  const glossary: Partial<StyleGlossary> = { keep: listOf(keep, /[,\n]/), corrections: parseCorrections(corr) };
  const dirty =
    JSON.stringify(p) !== JSON.stringify(st.profile) ||
    JSON.stringify(glossary.keep) !== JSON.stringify(st.glossary.keep) ||
    JSON.stringify(glossary.corrections) !== JSON.stringify(st.glossary.corrections);
  const save = async () => {
    try {
      fill(await api.saveMyStyle({ profile: p, glossary }));
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const start = async () => {
    try {
      fill(await api.startMyStyle());
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const setEx = (i: number, patch: Partial<StyleExample>) =>
    setP({ ...p, examples: p.examples.map((e, k) => (k === i ? { ...e, ...patch } : e)) });
  const add = () => {
    setP({ ...p, examples: [...p.examples, { format: "short", game: "", title: "", description: "", hashtags: [], tags: [], source: "manual" }] });
    setOpen(p.examples.length);
  };
  const gameName = (id: string) => st.games.find((g) => g.id === id)?.name ?? (id ? id.replace(/_/g, " ") : t("mystyle.any_game"));
  const shorts = p.examples.filter((e) => e.format === "short").length;
  return (
    <section className="card setting my-style">
      <div>
        <h2>{t("mystyle.title")}</h2>
        <p>{t("mystyle.desc")}</p>
        <p className="field-hint">{t("mystyle.private", { folder: st.folder })}</p>
      </div>
      <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
        {!p.examples.length ? (
          <div className="empty-inline">
            <p className="muted" style={{ margin: 0 }}>{t("mystyle.empty")}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-sm btn-primary" onClick={start}>
                {t("mystyle.start_sample")}
              </button>
              <button className="btn btn-sm" onClick={add}>
                <Icon name="plus" />
                {t("mystyle.add")}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="toggle-line">
              <span>{t("mystyle.enabled")}</span>
              <Toggle checked={p.enabled} onChange={(v) => setP({ ...p, enabled: v })} label={t("mystyle.enabled")} />
            </div>
            <div className="brand-grid">
              <label>
                <span className="field-label">{t("mystyle.name")}</span>
                <input className="input" value={p.name} placeholder="Your Name" onChange={(e) => setP({ ...p, name: e.target.value })} />
              </label>
              <label>
                <span className="field-label">{t("mystyle.channel_tag")}</span>
                <input className="input" value={p.channel_tag} placeholder="#MyChannel" onChange={(e) => setP({ ...p, channel_tag: e.target.value })} />
              </label>
            </div>
            <div className="toggle-line">
              <span>{t("mystyle.shorts_socials")}</span>
              <Toggle checked={p.shorts_socials} onChange={(v) => setP({ ...p, shorts_socials: v })} label={t("mystyle.shorts_socials")} />
            </div>
            <div className="toggle-line">
              <span>{t("mystyle.learn_likes")}</span>
              <Toggle checked={p.learn_likes} onChange={(v) => setP({ ...p, learn_likes: v })} label={t("mystyle.learn_likes")} />
            </div>
            <div>
              <span className="field-label">
                {t("mystyle.examples", { n: p.examples.length, shorts, long: p.examples.length - shorts })}
              </span>
              <ul className="style-examples">
                {p.examples.map((e, i) => (
                  <li key={e.id ?? `new-${i}`} className={open === i ? "open" : ""}>
                    <button type="button" className="style-ex-head" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
                      <span className="chip">{e.format === "short" ? "Shorts" : t("mystyle.long")}</span>
                      <span className="chip chip-outline">{gameName(e.game)}</span>
                      {e.source === "liked" && <span className="chip chip-success">👍</span>}
                      <span className="style-ex-title" dir="auto">{e.title || t("mystyle.untitled")}</span>
                      {e.views ? <span className="muted mono">{e.views}</span> : null}
                    </button>
                    {open === i && (
                      <div className="style-ex-body">
                        <div className="brand-grid">
                          <label>
                            <span className="field-label">{t("mystyle.format")}</span>
                            <Segmented<"short" | "long">
                              value={e.format}
                              options={[
                                { value: "short", label: "Shorts" },
                                { value: "long", label: t("mystyle.long") },
                              ]}
                              onChange={(v) => setEx(i, { format: v })}
                            />
                          </label>
                          <label>
                            <span className="field-label">{t("mystyle.game")}</span>
                            <input className="input" list="style-games" value={e.game} placeholder="lol / delta_force / ..." onChange={(x) => setEx(i, { game: x.target.value })} />
                          </label>
                        </div>
                        <label>
                          <span className="field-label">{t("mystyle.ex_title")}</span>
                          <input className="input" dir="auto" value={e.title} onChange={(x) => setEx(i, { title: x.target.value })} />
                          <span className="field-hint mono">{e.title.length} / 100</span>
                        </label>
                        <label>
                          <span className="field-label">{t("mystyle.ex_description")}</span>
                          <textarea className="textarea words-area" dir="auto" value={e.description} onChange={(x) => setEx(i, { description: x.target.value })} />
                        </label>
                        <label>
                          <span className="field-label">{t("mystyle.ex_hashtags")}</span>
                          <input className="input" value={e.hashtags.join(" ")} onChange={(x) => setEx(i, { hashtags: listOf(x.target.value, /\s+/) })} />
                        </label>
                        <label>
                          <span className="field-label">{t("mystyle.ex_tags")}</span>
                          <input className="input" value={e.tags.join(", ")} onChange={(x) => setEx(i, { tags: listOf(x.target.value, /,/) })} />
                        </label>
                        <div>
                          <button
                            className="btn btn-sm btn-ghost btn-danger-text"
                            onClick={() => {
                              setP({ ...p, examples: p.examples.filter((_, k) => k !== i) });
                              setOpen(null);
                            }}
                          >
                            <Icon name="trash" />
                            {t("mystyle.remove")}
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              <datalist id="style-games">
                {st.games.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </datalist>
              <button className="btn btn-sm" onClick={add}>
                <Icon name="plus" />
                {t("mystyle.add")}
              </button>
            </div>
            <details className="channel-heads">
              <summary>{t("mystyle.rules")}</summary>
              <ul className="style-rules">
                {["titles", "shorts", "long", "hashtags", "tags", "check"].map((k) => (
                  <li key={k}>{t(`mystyle.rule.${k}`)}</li>
                ))}
              </ul>
            </details>
          </>
        )}
        <label>
          <span className="field-label">{t("mystyle.keep")}</span>
          <textarea className="textarea words-area short" value={keep} onChange={(e) => setKeep(e.target.value)} />
          <span className="field-hint">{t("mystyle.keep_hint")}</span>
        </label>
        <label>
          <span className="field-label">{t("mystyle.corrections")}</span>
          <textarea className="textarea words-area short" value={corr} placeholder={"iki katil => double kill\nrevize => revive"} onChange={(e) => setCorr(e.target.value)} />
          <span className="field-hint">{t("mystyle.corrections_hint")}</span>
        </label>
        {st.glossary.learned.length > 0 && (
          <p className="field-hint">
            {t("mystyle.learned")}{" "}
            {st.glossary.learned
              .slice(-6)
              .map((x) => `${x.from} → ${x.to}`)
              .join(" · ")}
          </p>
        )}
        <div className="save-line">
          <span className="muted">{t("mystyle.applies")}</span>
          <button className="btn btn-primary btn-sm" disabled={!dirty} onClick={save}>
            {t("common.save")}
          </button>
        </div>
      </div>
    </section>
  );
}

/** Project page: title, description, hashtags and tags for the full stream as a long (16:9) video. */
export function LongMetaDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick } = useJobs();
  const [d, setD] = useState<LongMetadata | null | undefined>(undefined);
  const job = jobs.find((j) => j.kind === "long_metadata" && j.project_id === projectId && isActive(j));
  useEffect(() => {
    api
      .longMetadata(projectId)
      .then((r) => setD(r.long_metadata))
      .catch(() => setD(null));
  }, [projectId, finishedTick]);
  const make = async () => {
    try {
      await api.makeLongMetadata(projectId, !!d);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <Modal
      title={t("longmeta.title")}
      onClose={onClose}
      wide
      footer={
        <button className="btn btn-gold btn-sm" onClick={make} disabled={!!job}>
          <Icon name="sparkles" />
          {job ? t("longmeta.writing") : d ? t("longmeta.again") : t("longmeta.write")}
        </button>
      }
    >
      <p className="muted" style={{ marginTop: 0 }}>
        {t("longmeta.desc")}
      </p>
      {d === undefined ? null : !d ? (
        <p className="muted">{t("longmeta.none")}</p>
      ) : (
        <div style={{ display: "grid", gap: 14 }}>
          {d.profile === "sample" && <p className="field-hint">{t("longmeta.sample")}</p>}
          <div>
            <span className="field-label">{t("longmeta.titles")}</span>
            <ul className="long-titles">
              {d.titles.map((x) => (
                <li key={x}>
                  <span dir="auto">{x}</span>
                  <span className="muted mono">{x.length}</span>
                  <CopyButton text={x} />
                </li>
              ))}
            </ul>
          </div>
          <div>
            <span className="field-label">
              {t("longmeta.description")} <CopyButton text={d.description} />
            </span>
            <pre className="channel-preview" dir="auto">
              {d.description}
            </pre>
            <span className="field-hint">{t("longmeta.socials_hint")}</span>
          </div>
          <div>
            <span className="field-label">
              {t("longmeta.tags")} <CopyButton text={d.tags.join(", ")} />
            </span>
            <p className="mono" style={{ margin: 0, overflowWrap: "anywhere" }}>
              {d.tags.join(", ")}
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
}
