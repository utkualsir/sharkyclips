import { useEffect, useRef, useState } from "react";
import { api, urls, type ProjectSummary, type SwearLabels, type SwearScanView, type WordLists } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";

/** Studio > Word lists: the words learned from your manual bleeps / unbleeps, per language. */
export function LearnedWords({ data, code, onData }: { data: WordLists; code: string; onData: (d: WordLists) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const l = data.learned?.[code];
  const forget = async (word: string, kind: "add" | "ignore") => {
    try {
      onData(await api.forgetLearned(code, word, kind));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const row = (kind: "add" | "ignore") => {
    const list = l?.[kind] ?? [];
    if (!list.length) return <p className="muted small" style={{ margin: 0 }}>{t("words.learned_none")}</p>;
    return (
      <ul className="learned-list" lang={code}>
        {list.map((w) => (
          <li key={w.word}>
            <span dir="auto">{w.word}</span>
            <span className="muted small" title={Object.entries(w.spk).map(([k, v]) => `${k}: ${v}`).join(", ")}>
              {t("words.learned_times", { n: num(w.n) })}
            </span>
            <button className="btn btn-sm btn-ghost icon-btn" onClick={() => forget(w.word, kind)} aria-label={t("words.learned_forget")} title={t("words.learned_forget")}>
              <Icon name="x" />
            </button>
          </li>
        ))}
      </ul>
    );
  };
  return (
    <section className="card setting">
      <div>
        <h2>{t("words.learned")}</h2>
        <p>{t("words.learned_desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        <div>
          <span className="field-label">{t("words.learned_add")}</span>
          {row("add")}
        </div>
        <div>
          <span className="field-label">{t("words.learned_ignore")}</span>
          {row("ignore")}
        </div>
      </div>
    </section>
  );
}

const LABELS = ["yes", "no", "unsure"] as const;

/** Studio > Word lists: the review page of the swear check's "find everything" run. Each
 * candidate with listen buttons (as said / with the bleep) and a yes / no / unsure label. */
export function SwearCheckReview() {
  const { t } = useI18n();
  const toast = useToast();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [pid, setPid] = useState("");
  const [scan, setScan] = useState<SwearScanView | null>(null);
  const [labels, setLabels] = useState<SwearLabels | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, []);
  useEffect(() => {
    if (!pid) return;
    setScan(null);
    api.swearScan(pid).then(setScan).catch(() => setScan(null));
    api.swearLabels(pid).then(setLabels).catch(() => setLabels(null));
  }, [pid]);
  const play = (a: number, b: number, bleep?: [number, number] | null) => {
    audio.current?.pause();
    const q = `start=${a.toFixed(2)}&end=${b.toFixed(2)}${bleep ? `&bleep=${bleep[0]},${bleep[1]}` : ""}`;
    audio.current = new Audio(`${urls.source(pid).replace("/media/source", "/swearscan/snippet")}?${q}`);
    audio.current.play().catch(() => undefined);
  };
  const label = async (key: string, v: (typeof LABELS)[number]) => {
    try {
      setLabels(await api.setSwearLabel(pid, key, labels?.items[key]?.label === v ? null : v));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const items = scan?.items ?? [];
  return (
    <section className="card setting swear-check">
      <div>
        <h2>{t("swearcheck.title")}</h2>
        <p>{t("swearcheck.desc")}</p>
        <select className="select" value={pid} onChange={(e) => setPid(e.target.value)} aria-label={t("swearcheck.project")}>
          <option value="">{t("swearcheck.project")}</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title || p.id}
            </option>
          ))}
        </select>
      </div>
      <div>
        {pid && scan && !scan.done && <p className="muted small">{t("swearcheck.none")}</p>}
        {items.length > 0 && (
          <ul className="swear-list swear-check-list">
            {items.map((it) => {
              const key = it.start.toFixed(2);
              const lab = labels?.items[key];
              return (
                <li key={key} className={lab?.label === "yes" ? "on" : ""}>
                  <button className="btn btn-sm btn-ghost icon-btn" onClick={() => play(it.start - 1, it.end + 1)} aria-label={t("swearcheck.listen")} title={t("swearcheck.listen")}>
                    <Icon name="play" />
                  </button>
                  {it.bleep && (
                    <button className="btn btn-sm btn-ghost icon-btn" onClick={() => play(it.start - 1, it.end + 1, it.bleep)} aria-label={t("swearcheck.listen_bleep")} title={t("swearcheck.listen_bleep")}>
                      <Icon name="mic" />
                    </button>
                  )}
                  <span className="tc muted">{fmtTime(it.start, true)}</span>
                  <span className="swear-word" dir="auto" title={(it.heard ?? []).join(", ")}>
                    {it.word}
                  </span>
                  <span className={`badge swear-${it.status}`} title={`${it.votes ?? ""} ${it.why}`}>
                    {Math.round(it.score * 100)}
                  </span>
                  {lab?.note && <span className="muted small">{lab.note}</span>}
                  <span className="seg-mini" role="group" aria-label={t("swearcheck.label")}>
                    {LABELS.map((v) => (
                      <button key={v} type="button" className="btn btn-sm" aria-pressed={lab?.label === v} onClick={() => label(key, v)}>
                        {t(`swearcheck.${v}`)}
                      </button>
                    ))}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
