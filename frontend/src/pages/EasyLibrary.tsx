import { useCallback, useEffect, useState } from "react";
import { easyApi, urls, type EasyLibRow } from "../api";
import { Icon } from "../components/Icons";
import { fmtCompact, fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { href } from "../router";

type Tab = "ready" | "planned" | "live";
const TABS: Tab[] = ["ready", "planned", "live"];

/** Easy mode Library: three simple tabs, big thumbnails, minimal text. */
export default function EasyLibrary() {
  const { t, lang } = useI18n();
  const { finishedTick } = useJobs();
  const [tab, setTab] = useState<Tab>("ready");
  const [data, setData] = useState<Record<Tab, EasyLibRow[]> | null>(null);

  const load = useCallback(() => {
    easyApi
      .library()
      .then((d) => setData(d.tabs))
      .catch(() => setData({ ready: [], planned: [], live: [] }));
  }, []);
  useEffect(load, [load, finishedTick]);

  const rows = data?.[tab] ?? [];
  const when = (iso: string | null) =>
    iso
      ? new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso))
      : "";

  return (
    <main className="page ez-page">
      <div className="ez-hero">
        <h1 className="display">{t("easy.library_title")}</h1>
      </div>
      <div className="ez-tabs" role="tablist" aria-label={t("easy.library_title")}>
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            id={`ez-tab-${k}`}
            aria-selected={tab === k}
            aria-controls="ez-tabpanel"
            onClick={() => setTab(k)}
          >
            {t(`easy.tab_${k}`)}
            {data && <span className="ez-tab-count mono">{data[k].length}</span>}
          </button>
        ))}
      </div>
      <section id="ez-tabpanel" role="tabpanel" aria-labelledby={`ez-tab-${tab}`}>
        {data === null ? (
          <div className="ez-lib-grid">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" style={{ aspectRatio: "16 / 11", borderRadius: 14 }} />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="empty">
            <Icon name={tab === "live" ? "eye" : tab === "planned" ? "calendar" : "film"} size={30} />
            <h2 className="display">{t(`easy.lib_empty_${tab}`)}</h2>
            {tab === "ready" && (
              <a className="btn btn-primary btn-lg" href={href.library} style={{ marginTop: 8 }}>
                <Icon name="plus" /> {t("easy.new_video")}
              </a>
            )}
          </div>
        ) : (
          <ul className="ez-lib-grid">
            {rows.map((r) => (
              <li key={r.key} className="ez-lib-item">
                <a href={tab === "live" && r.url ? r.url : href.project(r.project_id)} target={tab === "live" && r.url ? "_blank" : undefined} rel="noreferrer">
                  <span className="ez-lib-thumb">
                    <img src={urls.clipThumb(r.project_id, r.clip_id)} alt="" loading="lazy" />
                    <span className="ez-dur mono">{fmtTime(r.duration)}</span>
                  </span>
                  <b className="ez-lib-title" dir="auto">
                    {r.title}
                  </b>
                  <span className="ez-lib-meta">
                    {tab === "live" ? (
                      <>
                        <Icon name="eye" size={15} />{" "}
                        {r.views != null ? t("easy.views", { n: r.views, v: fmtCompact(r.views, lang) }) : t("easy.views_soon")}
                        {r.status === "locked" && <span className="muted"> · {t("easy.live_private")}</span>}
                      </>
                    ) : tab === "planned" ? (
                      r.status === "failed" ? (
                        <span className="danger">
                          <Icon name="alert" size={15} /> {r.error?.message ?? t("common.error")}
                        </span>
                      ) : (
                        <>
                          <Icon name="calendar" size={15} /> {when(r.publish_at || r.date)}
                        </>
                      )
                    ) : (
                      <span className="muted" dir="auto">
                        {r.project_title}
                      </span>
                    )}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
