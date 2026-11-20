import { useEffect, useId, useMemo, useState } from "react";
import { api, type ReleaseEntry } from "../api";
import { useAppState } from "../appstate";
import { Icon } from "../components/Icons";
import { Markdown } from "../components/Shell";
import { useI18n } from "../i18n";

// 1.2.58: the "Updates" page. Every version from CHANGELOG.md, newest first: version, date, a
// short summary and the details grouped as New / Improved / Fixed, in the UI language (English
// where a translation is missing). Opening it clears the "New" badge on the menu item.

const KIND_ICON: Record<string, string> = { new: "sparkles", improved: "chart", fixed: "check", other: "list" };

function plain(md: string): string {
  return md.replace(/[*`#>[\]()_-]/g, " ").replace(/\s+/g, " ").toLowerCase();
}

export default function Updates() {
  const { t, lang } = useI18n();
  const { state, set } = useAppState();
  const [entries, setEntries] = useState<ReleaseEntry[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const searchId = useId();

  useEffect(() => {
    setFailed(false);
    api
      .releases(lang)
      .then((r) => setEntries(r.entries))
      .catch(() => setFailed(true));
  }, [lang]);

  useEffect(() => {
    if (state?.updates_new) api.updatesSeen(state.version).then(set).catch(() => {});
  }, [state?.updates_new]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = useMemo(() => {
    if (!entries) return null;
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) =>
      `${e.version} ${e.date ?? ""} ${plain(e.summary)} ${e.groups.map((g) => plain(g.markdown)).join(" ")}`.includes(q),
    );
  }, [entries, query]);

  const fmtDate = (d: string | null) => {
    if (!d) return "";
    try {
      return new Date(`${d}T12:00:00`).toLocaleDateString(`${lang}-u-nu-latn`, { year: "numeric", month: "long", day: "numeric" });
    } catch {
      return d;
    }
  };

  return (
    <main className="page updates-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("updates.title")}</h1>
          <p className="lede">{t("updates.lede")}</p>
        </div>
      </div>

      <div className="updates-search">
        <label htmlFor={searchId} className="visually-hidden">
          {t("updates.search")}
        </label>
        <Icon name="scan" size={16} />
        <input
          id={searchId}
          className="input"
          type="search"
          value={query}
          placeholder={t("updates.search")}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {failed && (
        <div className="notice notice-danger" role="alert">
          <Icon name="alert" />
          <div>{t("common.offline")}</div>
        </div>
      )}

      {shown === null && !failed ? (
        <div className="skeleton-lines">
          {[70, 90, 55, 80].map((w) => (
            <div key={w} className="skeleton" style={{ width: `${w}%` }} />
          ))}
        </div>
      ) : shown && shown.length === 0 ? (
        <p className="muted">{t("updates.none", { q: query.trim() })}</p>
      ) : (
        <ol className="updates-list" aria-label={t("updates.title")}>
          {(shown ?? []).map((e, i) => (
            <li key={e.version} className="card updates-item">
              <details open={i === 0 && !query}>
                <summary>
                  <span className="updates-head">
                    <b className="mono">{e.version}</b>
                    {e.version === state?.version && <span className="chip chip-gold">{t("updates.current")}</span>}
                    <span className="muted small">{fmtDate(e.date)}</span>
                  </span>
                  <span className="updates-summary" lang={e.summary_lang} dir={e.summary_lang === "ar" ? "rtl" : undefined}>
                    {e.summary}
                  </span>
                  <span className="updates-more small">
                    {t("updates.details")} <Icon name="chevron-down" size={14} />
                  </span>
                </summary>
                <div className="updates-body" lang={e.details_lang} dir={e.details_lang === "ar" ? "rtl" : undefined}>
                  {e.details_lang !== lang && <p className="muted small">{t("updates.english_only")}</p>}
                  {e.groups.map((g) => (
                    <section key={g.kind} className={`updates-group updates-${g.kind}`}>
                      <h3>
                        <Icon name={KIND_ICON[g.kind] ?? "list"} size={14} /> {t(`updates.kind.${g.kind}`)}
                      </h3>
                      <Markdown text={g.markdown} />
                    </section>
                  ))}
                </div>
              </details>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}
