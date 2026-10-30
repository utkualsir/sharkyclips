import { lazy, Suspense, useEffect, useState } from "react";
import { api } from "./api";
import { GovernorWidget } from "./components/Governor";
import { useAppState } from "./appstate";
import { BrandMark } from "./components/Brand";
import { Icon } from "./components/Icons";
import { DevBanner, Footer, WhatsNew } from "./components/Shell";
import Launch from "./components/Launch";
import { Onboarding } from "./components/Welcome";
import { jobLabel } from "./components/ui";
import { UI_LANGUAGES, useI18n } from "./i18n";
import { isActive, useJobs } from "./jobs";
import { chooseLanguage } from "./meta";
import Library from "./pages/Library";
import ProjectPage from "./pages/Project";
// Less used screens load when first opened (smaller start-up bundle).
const BestOf = lazy(() => import("./pages/BestOf"));
const GameDebug = lazy(() => import("./pages/GameDebug"));
const Studio = lazy(() => import("./pages/Studio"));
const Queue = lazy(() => import("./pages/Queue"));
const Stats = lazy(() => import("./pages/Stats"));
const ClipLibrary = lazy(() => import("./pages/ClipLibrary"));
const Stories = lazy(() => import("./pages/Stories"));
const Settings = lazy(() => import("./pages/Settings"));
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
      <a className="brand" href={href.library} aria-label="SharkyClips">
        <span className="brand-mark">
          <BrandMark />
        </span>
        <span className="brand-name">SharkyClips</span>
      </a>
      <nav className="nav">
        <a
          href={href.library}
          aria-current={["library", "project", "bestof", "game", "stories"].includes(route.name) ? "page" : undefined}
        >
          {t("nav.library")}
        </a>
        <a href={href.publish()} aria-current={route.name === "publish" ? "page" : undefined}>
          {t("nav.publish")}
        </a>
        <a href={href.queue} aria-current={route.name === "queue" ? "page" : undefined}>
          {t("nav.queue")}
          {active.length > 0 && <span className="nav-count mono">{active.length}</span>}
        </a>
        <a href={href.stats} aria-current={route.name === "stats" ? "page" : undefined}>
          {t("nav.stats")}
        </a>
        <a href={href.studio()} aria-current={route.name === "studio" ? "page" : undefined}>
          {t("nav.studio")}
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
        <GovernorWidget />
        {running && (
          <a
            className="job-pill"
            href={href.queue}
            title={t("jobs.running", { n: active.length })}
          >
            {running.paused ? <Icon name="pause" size={13} /> : <span className="spinner" style={{ width: 12, height: 12 }} />}
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

/** "Shutting down in 42 s" - visible on every page while the countdown runs. */
function ShutdownBanner() {
  const { t, num } = useI18n();
  const { shutdown, shutdownAt } = useJobs();
  const [, tick] = useState(0);
  const counting = shutdown?.countdown != null;
  useEffect(() => {
    if (!counting) return;
    const id = window.setInterval(() => tick((n) => n + 1), 250);
    return () => window.clearInterval(id);
  }, [counting]);
  if (!shutdown) return null;
  if (shutdown.countdown == null) {
    return shutdown.fired_at && shutdown.dry_run && Date.now() / 1000 - shutdown.fired_at < 20 ? (
      <div className="shutdown-banner" role="status">
        <Icon name="power" size={18} />
        <span>{t("shutdown.dry_fired")}</span>
      </div>
    ) : null;
  }
  const left = Math.max(0, Math.ceil(shutdown.countdown - (performance.now() - shutdownAt) / 1000));
  return (
    <div className="shutdown-banner" role="alert">
      <Icon name="power" size={18} />
      <span>
        <b>{t("shutdown.title")}</b> {t("shutdown.in", { s: num(left) })}
        {shutdown.dry_run && <span className="muted"> · {t("queue.shutdown_dry")}</span>}
      </span>
      <button className="btn btn-primary btn-sm" onClick={() => api.cancelShutdown()} autoFocus>
        {t("shutdown.cancel")}
      </button>
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const { state, set } = useAppState();
  const [splashDone, setSplashDone] = useState(false);
  const [onboarded, setOnboarded] = useState(false);
  const [manualWhatsNew, setManualWhatsNew] = useState(false);
  const [whatsNewClosed, setWhatsNewClosed] = useState(false);
  const showOnboarding = splashDone && !onboarded && !!state?.onboarding;
  const autoWhatsNew = splashDone && !showOnboarding && !!state?.whats_new && !whatsNewClosed;
  const closeWhatsNew = () => {
    if (autoWhatsNew && state?.whats_new) api.whatsNewSeen(state.whats_new).then(set).catch(() => {});
    setWhatsNewClosed(true);
    setManualWhatsNew(false);
  };
  return (
    <>
      <TopBar />
      <DevBanner />
      <ShutdownBanner />
      <div className="page-fx" key={route.name + ("id" in route ? `:${route.id}` : "")}>
        <Suspense fallback={null}>
        {route.name === "library" && <Library />}
        {route.name === "settings" && <Settings />}
        {route.name === "studio" && <Studio tab={route.tab} />}
        {route.name === "project" && <ProjectPage key={route.id} id={route.id} />}
        {route.name === "bestof" && <BestOf key={route.id} id={route.id} />}
        {route.name === "game" && <GameDebug key={route.id} id={route.id} />}
        {route.name === "stories" && <Stories key={route.id} id={route.id} />}
        {route.name === "queue" && <Queue />}
        {route.name === "stats" && <Stats />}
        {route.name === "publish" && <ClipLibrary view={route.view} />}
        </Suspense>
      </div>
      <Footer onWhatsNew={() => setManualWhatsNew(true)} />
      {(autoWhatsNew || manualWhatsNew) && state && (
        <WhatsNew version={state.whats_new ?? state.version} onClose={closeWhatsNew} />
      )}
      {showOnboarding && <Onboarding onDone={() => setOnboarded(true)} />}
      {!splashDone && <Launch onDone={() => setSplashDone(true)} />}
    </>
  );
}
