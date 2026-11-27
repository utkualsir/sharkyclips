// 1.2.68 Upload history: every clip shared from SharkyClips (and the ones you marked "I posted
// it"), newest first: date, game, clip, platform, link. Searchable. Kept after a project is
// deleted or its files are freed. 1.2.75: an "Uploads" tab with the stats (UploadStats.tsx).
import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { TARGET_NAME, type Target } from "../multipost";
import { shareApi, type HistoryRow } from "../share";
import { Icon } from "../components/Icons";
import { PlatformIcon } from "../components/PlatformIcons";
import { UploadStats } from "../components/UploadStats";

const ORDER: Target[] = ["youtube", "tiktok", "reels"];

type Tab = "list" | "stats";

export default function UploadHistory() {
  const { t } = useI18n();
  const [tab, choose] = useState<Tab>("list");
  return (
    <main className="page history-page">
      <h1 className="display">{t("history.title")}</h1>
      <div className="share-tabs history-tabs" role="tablist" aria-label={t("history.title")}>
        {(["list", "stats"] as Tab[]).map((x) => (
          <button
            key={x}
            type="button"
            role="tab"
            id={`history-tab-${x}`}
            aria-selected={tab === x}
            aria-controls={`history-panel-${x}`}
            tabIndex={tab === x ? 0 : -1}
            onClick={() => choose(x)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                const next = x === "list" ? "stats" : "list";
                choose(next);
                document.getElementById(`history-tab-${next}`)?.focus();
              }
            }}
          >
            <Icon name={x === "list" ? "list" : "chart"} size={14} /> {t(x === "list" ? "history.tab_list" : "history.tab_stats")}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`history-panel-${tab}`} aria-labelledby={`history-tab-${tab}`}>
        {tab === "list" ? <HistoryList /> : <UploadStats />}
      </div>
    </main>
  );
}

function HistoryList() {
  const { t, lang, num } = useI18n();
  const [q, setQ] = useState("");
  const [platform, setPlatform] = useState<Target | "">("");
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [all, setAll] = useState(0);
  useEffect(() => {
    const id = window.setTimeout(() => {
      shareApi
        .history(q, platform || undefined)
        .then((r) => {
          setRows(r.rows);
          setTotal(r.total);
          setAll(r.all);
        })
        .catch(() => setRows([]));
    }, 200);
    return () => window.clearTimeout(id);
  }, [q, platform]);
  const fmt = (iso: string) =>
    new Date(iso).toLocaleString(`${lang}-u-nu-latn`, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  return (
    <>
      <p className="muted" style={{ marginTop: 0, maxWidth: "70ch" }}>
        {t("history.lede")}
      </p>
      <div className="history-tools">
        <label className="field" style={{ flex: 1, minWidth: 200 }}>
          <span className="visually-hidden">{t("history.search")}</span>
          <input
            className="input"
            type="search"
            dir="auto"
            placeholder={t("history.search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <div className="share-tabs" role="group" aria-label={t("history.platform")}>
          <button type="button" aria-pressed={platform === ""} onClick={() => setPlatform("")}>
            {t("share.filter_all")}
          </button>
          {ORDER.map((p) => (
            <button key={p} type="button" aria-pressed={platform === p} onClick={() => setPlatform(p)}>
              <PlatformIcon p={p} size={14} /> {TARGET_NAME[p]}
            </button>
          ))}
        </div>
      </div>
      {rows === null ? (
        <div className="empty">
          <span className="spinner" />
        </div>
      ) : rows.length === 0 ? (
        <div className="empty">
          <Icon name="clock" size={28} />
          <p style={{ margin: 0 }}>{all ? t("history.none_found") : t("history.empty")}</p>
        </div>
      ) : (
        <>
          <p className="muted mono" aria-live="polite">
            {t("history.count", { n: num(total) })}
          </p>
          <div className="history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">{t("history.col_date")}</th>
                  <th scope="col">{t("history.col_game")}</th>
                  <th scope="col">{t("history.col_clip")}</th>
                  <th scope="col">{t("history.col_platform")}</th>
                  <th scope="col">{t("history.col_link")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key}>
                    <td className="mono" data-label={t("history.col_date")}>{fmt(r.at)}</td>
                    <td dir="auto" data-label={t("history.col_game")}>{r.game ?? "–"}</td>
                    <td dir="auto" data-label={t("history.col_clip")}>
                      <div className="history-clip">{r.title}</div>
                      <div className="muted history-stream" dir="auto">
                        {r.project_title}
                      </div>
                    </td>
                    <td data-label={t("history.col_platform")}>
                      <span className="history-plat">
                        <PlatformIcon p={r.platform} size={15} /> {TARGET_NAME[r.platform]}
                        {r.manual && <span className="chip chip-outline">{t("history.by_hand")}</span>}
                        {r.private && <span className="chip chip-outline">{t("history.private")}</span>}
                      </span>
                    </td>
                    <td data-label={t("history.col_link")}>
                      {r.url ? (
                        <a href={r.url} target="_blank" rel="noreferrer">
                          <Icon name="link" size={12} /> {t("history.open_post")}
                        </a>
                      ) : (
                        <span className="muted">–</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
