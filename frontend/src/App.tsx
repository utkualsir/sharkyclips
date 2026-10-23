import { BrandMark, Icon } from "./components/Icons";
import { jobLabel } from "./components/ui";
import { UI_LANGUAGES, useI18n } from "./i18n";
import { isActive, useJobs } from "./jobs";
import { chooseLanguage } from "./meta";
import Library from "./pages/Library";
import ProjectPage from "./pages/Project";
import Settings from "./pages/Settings";
import { href, useRoute } from "./router";
import { useTheme } from "./theme";

function TopBar() {
  const route = useRoute();
  const { t, lang, setLang, num } = useI18n();
  const [theme, , toggle] = useTheme();
  const { jobs, connected } = useJobs();
  const active = jobs.filter(isActive);
  const running = active.find((j) => j.status === "running") ?? active[0];

  return (
    <header className="topbar">
      <a className="brand" href={href.library} aria-label="ClipForge">
        <span className="brand-mark">
          <BrandMark />
        </span>
        <span className="brand-name">ClipForge</span>
      </a>
      <nav className="nav">
        <a href={href.library} aria-current={route.name !== "settings" ? "page" : undefined}>
          {t("nav.library")}
        </a>
        <a href={href.settings} aria-current={route.name === "settings" ? "page" : undefined}>
          {t("nav.settings")}
        </a>
      </nav>
      <div className="topbar-spacer" />
      <div className="topbar-actions">
        {!connected && (
          <span className="chip chip-danger" title={t("common.offline")}>
            <span className="dot" />
            offline
          </span>
        )}
        {running && (
          <a
            className="job-pill"
            href={running.project_id ? href.project(running.project_id) : href.library}
            title={t("jobs.running", { n: active.length })}
          >
            <span className="spinner" style={{ width: 12, height: 12 }} />
            <b>{jobLabel(running, t, num)}</b>
            {active.length > 1 && <span>+{active.length - 1}</span>}
          </a>
        )}
        <select
          className="select select-sm"
          style={{ width: "auto" }}
          value={lang}
          aria-label={t("lang.label")}
          onChange={(e) => chooseLanguage(e.target.value, setLang)}
        >
          {UI_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
        <button
          className="btn btn-ghost icon-btn"
          onClick={toggle}
          aria-label={t("theme.toggle")}
          title={theme === "dark" ? t("theme.light") : t("theme.dark")}
        >
          <Icon name={theme === "dark" ? "sun" : "moon"} />
        </button>
      </div>
    </header>
  );
}

export default function App() {
  const route = useRoute();
  return (
    <>
      <TopBar />
      {route.name === "library" && <Library />}
      {route.name === "settings" && <Settings />}
      {route.name === "project" && <ProjectPage key={route.id} id={route.id} />}
    </>
  );
}
