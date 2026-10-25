import { useEffect, useId, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { motion } from "../motion";
import { FIN_PATH, WAVE_PATH } from "./Brand";

// Launch sequence (~1.8 s, click / Esc skips):
//   water line draws across -> the fin rises out of it and glides, leaving a wake ->
//   a "cut" slash reveals the wordmark -> the slogan fades in -> the logo and the wordmark fly
//   into the header (shared element), the app fades in underneath.
// The launcher's splash page (backend/sharkyclips/web/splash.html, same markup + CSS) plays the
// intro while the server starts, then opens the app with ?splash=done; index.html paints the
// last frame (#boot-launch) and this component flies it into the header. Keep all three in sync.

const INTRO_MS = 1800;
const FLY_MS = 640;
const SESSION_KEY = "sc-splash-shown";
const EASE = "cubic-bezier(0.2, 0.7, 0.2, 1)";

function shownThisSession(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

function markShown() {
  try {
    sessionStorage.setItem(SESSION_KEY, "1");
  } catch {
    /* private mode */
  }
}

function center(r: DOMRect) {
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

/** Fly the launch logo + wordmark into the header, fade the rest. Calls done() at the end. */
export function handoff(root: HTMLElement, done: () => void, own = false) {
  const html = document.documentElement;
  const level = motion();
  const finish = () => {
    html.classList.remove("launch-handoff", "boot-handover");
    if (own) root.remove(); // index.html's copy; React removes its own
    done();
    window.setTimeout(() => html.classList.remove("app-enter"), 900);
  };
  if (level !== "full") {
    root.animate([{ opacity: 1 }, { opacity: 0 }], { duration: level === "off" ? 0 : 260, fill: "forwards" })
      .finished.then(finish, finish);
    return;
  }
  const mark = root.querySelector<SVGElement>(".launch-mark");
  const word = root.querySelector<HTMLElement>(".launch-word-text");
  const headMark = document.querySelector<SVGElement>(".topbar .brand-mark svg");
  const headWord = document.querySelector<HTMLElement>(".topbar .brand-name");
  html.classList.add("launch-handoff", "app-enter");
  const opts: KeyframeAnimationOptions = { duration: FLY_MS, easing: EASE, fill: "forwards" };
  const anims: Animation[] = [];
  const fly = (el: Element | null, target: Element | null, scaleBy: "width" | "height") => {
    if (!el || !target) return;
    const a = el.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    if (!a.width || !b.width || getComputedStyle(target).display === "none") {
      anims.push(el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 220, fill: "forwards" }));
      return;
    }
    const ca = center(a);
    const cb = center(b);
    const s = scaleBy === "width" ? b.width / a.width : b.height / a.height;
    anims.push(
      el.animate(
        [{ transform: "translate(0, 0) scale(1)" }, { transform: `translate(${cb.x - ca.x}px, ${cb.y - ca.y}px) scale(${s})` }],
        opts,
      ),
    );
  };
  fly(mark, headMark, "width");
  fly(word, headWord, "height");
  const mini = root.querySelector(".launch-mini-wave");
  if (mini) anims.push(mini.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, delay: 60, fill: "forwards" }));
  const solid = root.querySelector(".launch-fin-solid");
  if (solid) anims.push(solid.animate([{ opacity: 0 }, { opacity: 1 }], { ...opts, duration: FLY_MS * 0.8 }));
  root.querySelectorAll(".launch-water, .launch-slogan, .launch-hint, .launch-slash, .launch-wake").forEach((el) =>
    anims.push(el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, fill: "forwards", easing: "ease-out" })),
  );
  anims.push(
    root.animate([{ backgroundColor: getComputedStyle(root).backgroundColor }, { backgroundColor: "transparent" }], {
      duration: 420,
      delay: 140,
      easing: "ease-out",
      fill: "forwards",
    }),
  );
  root.style.pointerEvents = "none";
  Promise.all(anims.map((a) => a.finished)).then(finish, finish);
}

/** The launch markup: the same in splash.html and index.html (#boot-launch). */
export function LaunchStage({ slogan, hint, idBase }: { slogan: string; hint?: string; idBase: string }) {
  return (
    <>
      <div className="launch-stage">
        <div className="launch-mark-wrap">
          <svg className="launch-water" viewBox="0 0 1200 12" preserveAspectRatio="none" aria-hidden="true">
            <path
              d={"M0 6" + " q15 -3.2 30 0 t30 0".repeat(20)}
              pathLength={1}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <svg className="launch-mark" viewBox="6 8 52 48" aria-hidden="true">
            <defs>
              <linearGradient id={`${idBase}-fin`} x1="0" y1="0" x2="0.35" y2="1">
                <stop offset="0" className="launch-fin-a" />
                <stop offset="1" className="launch-fin-b" />
              </linearGradient>
              <clipPath id={`${idBase}-air`}>
                <rect x="-40" y="-20" width="140" height="70" />
              </clipPath>
            </defs>
            <path className="launch-wake" d="M12.5 50.2 Q6 48.6 -1 50 M14 52.6 Q7 52.4 1 54" pathLength={1} />
            <path className="launch-mini-wave" d={WAVE_PATH} />
            <g clipPath={`url(#${idBase}-air)`}>
              <g className="launch-fin">
                <path fillRule="evenodd" d={FIN_PATH} fill={`url(#${idBase}-fin)`} />
                <path className="launch-fin-solid" fillRule="evenodd" d={FIN_PATH} />
              </g>
            </g>
          </svg>
        </div>
        <div className="launch-word" dir="ltr">
          <span className="launch-word-text">SharkyClips</span>
          <span className="launch-slash" aria-hidden="true" />
        </div>
        <p className="launch-slogan">{slogan}</p>
      </div>
      {hint && <span className="launch-hint">{hint}</span>}
    </>
  );
}

/** In-app launch: plays once per browser session (the launcher's splash page counts), or
 * takes over index.html's last frame after the launcher's splash page. */
export default function Launch({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const idBase = useId().replace(/:/g, "");
  const ref = useRef<HTMLDivElement>(null);
  const [mode] = useState<"handover" | "skip" | "play">(() => {
    if (document.documentElement.classList.contains("boot-handover") && document.getElementById("boot-launch"))
      return "handover";
    document.getElementById("boot-launch")?.remove(); // index.html's copy is only for the hand-over
    if (shownThisSession() || motion() === "off") return "skip";
    return "play";
  });
  const started = useRef(false);

  useEffect(() => {
    markShown();
    if (mode === "skip") {
      document.getElementById("boot-launch")?.remove();
      onDone();
      return;
    }
    if (mode === "handover") {
      const url = new URL(window.location.href);
      url.searchParams.delete("splash");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
      const boot = document.getElementById("boot-launch")!;
      // Wait one frame so the header is laid out, plus the web fonts (max 300 ms).
      const go = () => {
        if (started.current) return;
        started.current = true;
        requestAnimationFrame(() => handoff(boot, onDone, true));
      };
      Promise.race([document.fonts?.ready ?? Promise.resolve(), new Promise((r) => setTimeout(r, 300))]).then(go);
      return;
    }
    const root = ref.current!;
    const leave = () => {
      if (started.current) return;
      started.current = true;
      root.classList.add("launch-static"); // jump to the last frame (skip)
      requestAnimationFrame(() => handoff(root, onDone));
    };
    const id = window.setTimeout(leave, motion() === "full" ? INTRO_MS : 900);
    const key = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "Enter" || e.key === " ") && leave();
    root.addEventListener("click", leave);
    window.addEventListener("keydown", key);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("keydown", key);
      root.removeEventListener("click", leave);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (mode !== "play") return null;
  return (
    <div className="launch" ref={ref} role="status" aria-live="polite" aria-label="SharkyClips">
      <LaunchStage slogan={t("brand.slogan")} hint={t("splash.skip")} idBase={idBase} />
    </div>
  );
}
