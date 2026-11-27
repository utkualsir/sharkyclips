// 1.2.75 "Uploads" tab of the History page: my uploads today / this week / in total, per platform
// (YouTube, Instagram, TikTok, by hand), and a 14-day bar chart. Pointing at, focusing or tapping
// any number or bar shows its posts (clip, time, platform, link, status) in the details panel
// below; the panel stays until another number is picked, so its links can be clicked.
import { useEffect, useMemo, useState } from "react";
import "../uploads.css";
import { useI18n } from "../i18n";
import { TARGET_NAME } from "../multipost";
import { GROUPS, uploadsApi, type Group, type StatBucket, type StatItem, type UploadStats as Stats } from "../uploads";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { YouTubeQuota } from "./YouTubeQuota";

type Period = "today" | "week" | "total";
type Pick = { kind: Period | "day"; date?: string; group?: Group };

const sameKey = (a: Pick, b: Pick) => a.kind === b.kind && a.date === b.date && a.group === b.group;

export function UploadStats() {
  const { t, lang, num } = useI18n();
  const [s, setS] = useState<Stats | null>(null);
  const [pick, setPick] = useState<Pick>({ kind: "today" });
  useEffect(() => {
    let alive = true;
    const load = () =>
      uploadsApi
        .stats()
        .then((x) => alive && setS(x))
        .catch(() => alive && setS(null));
    load();
    window.addEventListener("sc-share-changed", load);
    return () => {
      alive = false;
      window.removeEventListener("sc-share-changed", load);
    };
  }, []);
  const dayFmt = (d: string, long = false) =>
    new Date(`${d}T12:00:00`).toLocaleDateString(`${lang}-u-nu-latn`, long ? { weekday: "long", day: "numeric", month: "long" } : { day: "numeric", month: "short" });
  const timeFmt = (iso: string) =>
    new Date(iso).toLocaleString(`${lang}-u-nu-latn`, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const gName = (g: Group) => t(`ups.g_${g}`);

  const picked = useMemo(() => {
    if (!s) return null;
    const bucket: StatBucket | undefined = pick.kind === "day" ? s.days.find((d) => d.date === pick.date) : s[pick.kind];
    if (!bucket) return null;
    const items = pick.group ? bucket.items.filter((i) => i.group === pick.group) : bucket.items;
    const n = pick.group ? bucket.by[pick.group] : bucket.total;
    const when = pick.kind === "day" ? dayFmt(pick.date!, true) : t(`ups.${pick.kind}`);
    return { items, n, label: pick.group ? `${when} · ${gName(pick.group)}` : when };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s, pick, lang]);

  if (!s) return <div className="empty"><span className="spinner" /></div>;

  // hover, keyboard focus and tap all pick the same thing
  const pickProps = (p: Pick) => ({
    onMouseEnter: () => setPick(p),
    onFocus: () => setPick(p),
    onClick: () => setPick(p),
    "aria-pressed": sameKey(pick, p),
    "aria-controls": "ups-details",
  });
  const max = Math.max(1, ...s.days.map((d) => d.total));
  const periods: Period[] = ["today", "week", "total"];

  return (
    <div className="ups">
      <div className="ups-top">
        <div className="ups-tiles">
          {periods.map((p) => (
            <div key={p} className="ups-tile">
              <button type="button" className="ups-num" {...pickProps({ kind: p })}>
                <span className="ups-label">{t(`ups.${p}`)}</span>
                <b className="mono">{num(s[p].total)}</b>
                {p === "week" && <span className="muted ups-sub">{t("ups.week_from", { date: dayFmt(s.week.from) })}</span>}
              </button>
              <ul className="ups-groups">
                {GROUPS.map((g) => (
                  <li key={g}>
                    <button type="button" className="ups-g" data-g={g} {...pickProps({ kind: p, group: g })}>
                      <span className="ups-sw" aria-hidden="true" />
                      <span className="ups-gname">{gName(g)}</span>
                      <b className="mono">{num(s[p].by[g])}</b>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="card ups-quota">
          <YouTubeQuota />
        </div>
      </div>

      <figure className="card ups-chart">
        <figcaption>
          <b>{t("ups.chart")}</b>
          <ul className="ups-legend" aria-label={t("ups.legend")}>
            {GROUPS.map((g) => (
              <li key={g} data-g={g}>
                <span className="ups-sw" aria-hidden="true" /> {gName(g)}
              </li>
            ))}
          </ul>
        </figcaption>
        <div className="ups-bars" role="group" aria-label={t("ups.chart_label")}>
          {s.days.map((d) => (
            <button
              key={d.date}
              type="button"
              className="ups-bar"
              aria-label={`${dayFmt(d.date, true)}: ${t("ups.n_uploads", { n: num(d.total) })}`}
              {...pickProps({ kind: "day", date: d.date })}
            >
              <span className="ups-stack" style={{ height: `${(d.total / max) * 100}%` }} aria-hidden="true">
                {GROUPS.filter((g) => d.by[g] > 0).map((g) => (
                  <span key={g} data-g={g} style={{ flexGrow: d.by[g] }} />
                ))}
              </span>
              <span className="ups-day mono" aria-hidden="true">
                {new Date(`${d.date}T12:00:00`).toLocaleDateString(`${lang}-u-nu-latn`, { day: "numeric" })}
              </span>
            </button>
          ))}
        </div>
      </figure>

      <section className="card ups-details" id="ups-details" aria-live="polite">
        <h2>
          {t("ups.details_for", { what: picked?.label ?? "", n: num(picked?.n ?? 0) })}
        </h2>
        <p className="muted ups-hint">{t("ups.details_hint")}</p>
        {!picked || picked.items.length === 0 ? (
          <p className="muted">{s.total.total ? t("ups.none") : t("ups.empty")}</p>
        ) : (
          <ul className="ups-list ups-scroll">
            {picked.items.map((i: StatItem) => (
              <li key={i.key} className="ups-item">
                <span className="ups-sw" data-g={i.group} aria-hidden="true" />
                <div className="ups-item-main">
                  <div className="ups-item-title" dir="auto">{i.title}</div>
                  <div className="muted ups-item-sub" dir="auto">
                    {[i.project_title, i.game].filter(Boolean).join(" · ")}
                  </div>
                </div>
                <span className="mono ups-item-at">{timeFmt(i.at)}</span>
                <span className="ups-item-plat">
                  <PlatformIcon p={i.platform} size={14} /> {TARGET_NAME[i.platform]}
                </span>
                <span className="chip chip-outline">{t(`ups.status_${i.status}`)}</span>
                {i.url ? (
                  <a href={i.url} target="_blank" rel="noreferrer" className="ups-item-link">
                    <Icon name="link" size={12} /> {t("history.open_post")}
                  </a>
                ) : (
                  <span className="muted ups-item-link">–</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
