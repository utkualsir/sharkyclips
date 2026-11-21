import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { miniGameApi, type MiniGameStats } from "../api";
import { Icon } from "../components/Icons";
import { useI18n } from "../i18n";
import { setGameKeyHandler, GAME_ROOT_ATTR } from "../keyguard";
import { useMotion } from "../motion";
import { go, href } from "../router";
import { createGame, H, startRound, stats as roundStats, step, W, type Game, type Input, type PowerKind } from "./engine";
import { draw, drawPreview, SKINS } from "./render";
import { playEvents, setSound, suspendSound } from "./sfx";
import "./minigame.css";

// 1.2.59: the waiting mini game panel. A compact panel at the bottom left (it never covers the
// top bar's job progress and shows the job's progress itself). The game runs only while the panel
// is open, the window is visible and focused, and a round is being played; everything else is a
// still picture. Rounds, scores and skins go to the local server (minigame.py), never online.

type Screen = "howto" | "start" | "play" | "paused" | "over" | "skins";
interface Props {
  open: boolean;
  progress: { label: string; pct: number | null } | null;
  ready: { projectId: string; ok: boolean } | null;
  onClose: () => void;
  onReadySeen: () => void;
}

const STEP = 1 / 60;
const MIN_FRAME_MS = 1000 / 61; // 60 fps at most, also on 120 / 144 Hz screens
const POWER_ICON: Record<PowerKind, string> = { magnet: "target", frenzy: "zap", shield: "lock", time: "clock" };

// The game lives in this module, so closing the panel (or changing the page) keeps the round.
let game: Game | null = null;
let lastStats: MiniGameStats | null = null;

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface Hud {
  score: number;
  time: number;
  lives: number;
  combo: number;
  mult: number;
  power: PowerKind | null;
  shield: boolean;
}

function hudOf(g: Game): Hud {
  const power: PowerKind | null = g.frenzy > 0 ? "frenzy" : g.magnet > 0 ? "magnet" : null;
  return {
    score: Math.round(g.score), time: Math.ceil(g.timeLeft), lives: g.lives, combo: g.combo,
    mult: (1 + Math.min(4, Math.floor(g.combo / 4))) * (g.frenzy > 0 ? 2 : 1), power, shield: g.shield,
  };
}

const sameHud = (a: Hud, b: Hud) =>
  a.score === b.score && a.time === b.time && a.lives === b.lives && a.combo === b.combo && a.mult === b.mult &&
  a.power === b.power && a.shield === b.shield;

export default function Panel({ open, progress, ready, onClose, onReadySeen }: Props) {
  const { t, num } = useI18n();
  const motion = useMotion();
  if (!game) game = createGame((Date.now() & 0xffffff) + 1);
  const g = game;
  const [stats, setStats] = useState<MiniGameStats | null>(lastStats);
  const [screen, setScreen] = useState<Screen>(() => (g.phase === "playing" ? "paused" : g.phase === "over" ? "over" : "start"));
  const [hud, setHud] = useState<Hud>(() => hudOf(g));
  const [result, setResult] = useState<MiniGameStats["round"] | null>(null);
  const [announce, setAnnounce] = useState("");
  const [focused, setFocused] = useState(true);
  const canvas = useRef<HTMLCanvasElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const keys = useRef<Set<string>>(new Set());
  const pointer = useRef<{ x: number; y: number } | null>(null);
  const dashReq = useRef(false);
  const perf = useRef({ ms: 0, fps: 0, frames: 0, quality: 1 });
  const screenRef = useRef(screen);
  screenRef.current = screen;
  const skin = SKINS[stats?.skin ?? "classic"] ?? SKINS.classic;
  const muted = stats?.muted !== false;

  // ---------------------------------------------------------------- numbers from the server
  useEffect(() => {
    miniGameApi
      .get(today())
      .then((s) => {
        lastStats = s;
        setStats(s);
        if (!s.howto_seen && g.phase !== "playing") setScreen("howto");
      })
      .catch(() => {});
  }, [g]);
  useEffect(() => setSound(open && !muted), [open, muted]);

  const savePrefs = (p: { skin?: string; muted?: boolean; howto_seen?: boolean }) => {
    setStats((s) => (s ? { ...s, ...p } : s));
    miniGameApi
      .prefs({ ...p, today: today() })
      .then((s) => {
        lastStats = s;
        setStats(s);
      })
      .catch(() => {});
  };

  // ---------------------------------------------------------------- drawing
  const size = useRef({ css: 0, px: 0 });
  const paint = useCallback(() => {
    const c = canvas.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const q = perf.current.quality;
    draw(ctx, g, { scale: c.width / W, skin, motion, quality: q });
  }, [g, skin, motion]);

  useLayoutEffect(() => {
    const c = canvas.current;
    const box = host.current;
    if (!c || !box) return;
    const fit = () => {
      const css = Math.max(200, Math.floor(box.clientWidth));
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const px = Math.round(css * dpr);
      if (px === size.current.px) return;
      size.current = { css, px };
      c.width = px;
      c.height = Math.round((px * H) / W);
      c.style.height = `${Math.round((css * H) / W)}px`;
      paint();
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(box);
    return () => ro.disconnect();
  }, [paint, open]);

  // ---------------------------------------------------------------- pausing
  const pause = useCallback(() => {
    if (screenRef.current === "play") setScreen("paused");
    keys.current.clear();
    suspendSound();
  }, []);
  useEffect(() => {
    const vis = () => document.hidden && pause();
    const blur = () => {
      setFocused(false);
      pause();
    };
    const focus = () => setFocused(true);
    document.addEventListener("visibilitychange", vis);
    window.addEventListener("blur", blur);
    window.addEventListener("focus", focus);
    return () => {
      document.removeEventListener("visibilitychange", vis);
      window.removeEventListener("blur", blur);
      window.removeEventListener("focus", focus);
    };
  }, [pause]);
  useEffect(() => {
    if (!open) pause();
    else window.setTimeout(() => host.current?.focus({ preventScroll: true }), 0);
  }, [open, pause]);
  // the job is done: stop the round (the score stays) and say so
  useEffect(() => {
    if (!ready || !open) return;
    pause();
    setAnnounce(ready.ok ? t("mg.ready") : t("mg.failed"));
  }, [ready, open, pause, t]);

  // ---------------------------------------------------------------- round end
  const finish = useCallback(() => {
    const s = roundStats(g);
    setScreen("over");
    setResult({ score: s.score, new_best: false, new_today: false, new_skins: [] });
    setAnnounce(t("mg.status_over", { score: num(s.score) }));
    miniGameApi
      .round({ score: s.score, fish: s.fish, combo: s.bestCombo, date: today() })
      .then((r) => {
        lastStats = r;
        setStats(r);
        setResult(r.round ?? null);
      })
      .catch(() => {});
  }, [g, t, num]);

  // ---------------------------------------------------------------- the loop (only while playing)
  const playing = open && screen === "play" && focused && !ready;
  useEffect(() => {
    if (!playing) {
      paint();
      return;
    }
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    let lastDraw = 0;
    let slow = 0;
    let fast = 0;
    let shown = hudOf(g);
    let hudAt = 0;
    let fpsAt = last;
    let frames = 0;
    g.maxParticles = motion === "full" ? 160 : 60;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (now - lastDraw < MIN_FRAME_MS - 1) return;
      lastDraw = now;
      const t0 = performance.now();
      acc += Math.min(0.1, (now - last) / 1000);
      last = now;
      const k = keys.current;
      const input: Input = {
        tx: pointer.current?.x ?? null, ty: pointer.current?.y ?? null,
        dx: (k.has("right") ? 1 : 0) - (k.has("left") ? 1 : 0), dy: (k.has("down") ? 1 : 0) - (k.has("up") ? 1 : 0),
        dash: dashReq.current,
      };
      let n = 0;
      while (acc >= STEP && n < 4) {
        step(g, STEP, input);
        input.dash = false;
        dashReq.current = false;
        acc -= STEP;
        n++;
      }
      if (n === 4) acc = 0; // far behind (a slow moment): skip ahead, never spiral
      if (g.events.length) {
        playEvents(g.events);
        const over = g.events.some((e) => e.type === "over");
        g.events.length = 0;
        if (over) {
          paint();
          finish();
          return;
        }
      }
      paint();
      // cost of this frame (simulation + drawing); the picture gets simpler when it is too high
      const ms = performance.now() - t0;
      const p = perf.current;
      p.ms = p.ms ? p.ms * 0.95 + ms * 0.05 : ms;
      if (ms > 6) slow++;
      else if (ms < 2.5) fast++;
      if (slow > 20 && p.quality > 0) {
        p.quality = 0;
        g.maxParticles = 50;
        slow = 0;
      } else if (fast > 600 && p.quality < 1 && motion === "full") {
        p.quality = 1;
        g.maxParticles = 160;
        fast = 0;
      }
      frames++;
      if (now - fpsAt >= 1000) {
        p.fps = Math.round((frames * 1000) / (now - fpsAt));
        frames = 0;
        fpsAt = now;
        host.current?.setAttribute("data-frame-ms", p.ms.toFixed(3));
        host.current?.setAttribute("data-fps", String(p.fps));
        host.current?.setAttribute("data-quality", String(p.quality));
      }
      if (now - hudAt > 100) {
        hudAt = now;
        const h = hudOf(g);
        if (!sameHud(h, shown)) setHud((shown = h));
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [playing, g, paint, finish, motion]);

  // ---------------------------------------------------------------- actions
  const begin = useCallback(() => {
    startRound(g);
    setResult(null);
    setHud(hudOf(g));
    setScreen("play");
    host.current?.focus({ preventScroll: true });
  }, [g]);
  const resume = useCallback(() => {
    if (g.phase !== "playing") return;
    setScreen("play");
    host.current?.focus({ preventScroll: true });
  }, [g]);
  const togglePause = () => (screen === "play" ? pause() : screen === "paused" ? resume() : undefined);
  const toggleMute = () => {
    const m = !muted;
    setSound(open && !m);
    savePrefs({ muted: m });
  };
  const closeHowto = () => {
    savePrefs({ howto_seen: true });
    setScreen(g.phase === "playing" ? "paused" : "start");
  };

  // keys: only those typed inside the panel arrive here (keyguard.ts); none of them reach the app
  const keyRef = useRef<(e: KeyboardEvent) => void>(() => {});
  keyRef.current = (e: KeyboardEvent) => {
    const onButton = e.target instanceof HTMLElement && e.target.closest("button, a, input, select, textarea");
    const k = e.key;
    const dir =
      k === "ArrowLeft" || k === "a" || k === "A" ? "left"
      : k === "ArrowRight" || k === "d" || k === "D" ? "right"
      : k === "ArrowUp" || k === "w" || k === "W" ? "up"
      : k === "ArrowDown" || k === "s" || k === "S" ? "down" : null;
    if (e.type === "keyup") {
      if (dir) keys.current.delete(dir);
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (dir) {
      if (!onButton || k.startsWith("Arrow")) e.preventDefault();
      if (screenRef.current === "play") keys.current.add(dir);
      return;
    }
    if (k === " " || k === "Shift") {
      if (onButton && k === " ") return; // Space presses the focused button
      e.preventDefault();
      if (screenRef.current === "play") dashReq.current = true;
      else if (!e.repeat && (screenRef.current === "start" || screenRef.current === "over")) begin();
      else if (!e.repeat && screenRef.current === "paused") resume();
    } else if (k === "Enter" && !onButton) {
      if (screenRef.current === "start" || screenRef.current === "over") begin();
      else if (screenRef.current === "paused") resume();
    } else if (k === "p" || k === "P") {
      if (screenRef.current === "play") pause();
      else if (screenRef.current === "paused") resume();
    } else if (k === "m" || k === "M") toggleMute();
    else if (k === "Escape") {
      e.preventDefault();
      if (screenRef.current === "play") pause();
      else if (screenRef.current === "skins" || screenRef.current === "howto") setScreen(g.phase === "playing" ? "paused" : "start");
      else onClose();
    }
  };
  useEffect(() => {
    setGameKeyHandler((e) => keyRef.current(e));
    return () => setGameKeyHandler(null);
  }, []);

  // pointer: the shark swims to the mouse / finger
  const toWorld = (e: RPointerEvent) => {
    const r = canvas.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
  };
  const onPointerMove = (e: RPointerEvent) => {
    if (e.pointerType === "mouse" || e.buttons) pointer.current = toWorld(e);
  };
  const onPointerDown = (e: RPointerEvent) => {
    host.current?.focus({ preventScroll: true });
    if (screen !== "play") return;
    pointer.current = toWorld(e);
    if (e.pointerType !== "mouse") (e.target as Element).setPointerCapture?.(e.pointerId);
    else if (e.button === 0 && e.detail >= 2) dashReq.current = true; // double click: dash
  };
  const onPointerUp = (e: RPointerEvent) => {
    if (e.pointerType !== "mouse") pointer.current = null;
  };

  const best = stats?.best ?? 0;
  const pct = progress?.pct != null ? Math.round(progress.pct * 100) : null;
  const skinName = (id: string) => t(`mg.skin.${id}`);
  const rule = (s: MiniGameStats["skins"][number]) =>
    s.rule === "rounds" ? t("mg.rule_rounds", { n: num(s.need), have: num(s.have) })
    : s.rule === "fish" ? t("mg.rule_fish", { n: num(s.need), have: num(s.have) })
    : s.rule === "best" ? t("mg.rule_best", { n: num(s.need) })
    : s.rule === "combo" ? t("mg.rule_combo", { n: num(s.need) }) : "";

  return (
    <section className="mg-panel" {...{ [GAME_ROOT_ATTR]: "" }} hidden={!open} aria-label={t("mg.region")}>
      <header className="mg-head">
        <b className="mg-title">{t("mg.title")}</b>
        <div className="mg-head-btns">
          <button
            type="button"
            className="btn btn-ghost icon-btn mg-icon"
            onClick={togglePause}
            disabled={screen !== "play" && screen !== "paused"}
            aria-label={screen === "play" ? t("mg.pause") : t("mg.resume")}
            title={screen === "play" ? t("mg.pause") : t("mg.resume")}
          >
            <Icon name={screen === "play" ? "pause" : "play"} size={15} />
          </button>
          <button
            type="button"
            className="btn btn-ghost icon-btn mg-icon"
            onClick={toggleMute}
            aria-pressed={!muted}
            aria-label={t("mg.sound")}
            title={muted ? t("mg.unmute") : t("mg.mute")}
          >
            <Icon name={muted ? "volume-x" : "volume"} size={15} />
          </button>
          <button
            type="button"
            className="btn btn-ghost icon-btn mg-icon"
            onClick={() => {
              pause();
              setScreen("howto");
            }}
            aria-label={t("mg.howto_title")}
            title={t("mg.howto_title")}
          >
            <span aria-hidden="true" className="mg-q">?</span>
          </button>
          <button type="button" className="btn btn-ghost icon-btn mg-icon" onClick={onClose} aria-label={t("mg.close")} title={t("mg.close")}>
            <Icon name="minus" size={15} />
          </button>
        </div>
      </header>
      {progress && (
        <div className="mg-job">
          <span className="mg-job-label">{progress.label}</span>
          <div className="mg-job-bar" role="progressbar" aria-label={t("mg.working")} aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={pct ?? undefined}>
            <span style={{ width: `${pct ?? 30}%` }} className={pct == null ? "indet" : undefined} />
          </div>
        </div>
      )}
      <div className="mg-hud" aria-hidden={screen !== "play" && screen !== "paused"}>
        <span>
          {t("mg.score")} <b className="mono">{num(hud.score)}</b>
        </span>
        <span>
          {t("mg.time")} <b className="mono">{num(hud.time)}</b>
        </span>
        <span className="mg-lives" role="img" aria-label={`${t("mg.lives")}: ${hud.lives}`}>
          {[0, 1, 2].map((i) => (
            <span key={i} className={i < hud.lives ? "on" : ""} aria-hidden="true">♥</span>
          ))}
          {hud.shield && <Icon name="lock" size={12} />}
        </span>
        {hud.mult > 1 && <span className="mg-mult mono">x{hud.mult}</span>}
        {hud.power && <Icon name={POWER_ICON[hud.power]} size={13} />}
      </div>
      <div
        ref={host}
        className="mg-stage"
        tabIndex={0}
        role="application"
        aria-label={t("mg.canvas_label")}
        aria-describedby="mg-keys"
        data-screen={screen}
        onPointerMove={onPointerMove}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerLeave={(e) => e.pointerType === "mouse" && (pointer.current = null)}
      >
        <canvas ref={canvas} aria-hidden="true" />
        {screen === "play" && (
          <button type="button" className="mg-dash" onPointerDown={(e) => (e.stopPropagation(), (dashReq.current = true))}
            onClick={() => (dashReq.current = true)} aria-label={t("mg.dash")}>
            <Icon name="zap" size={18} />
          </button>
        )}
        {screen !== "play" && (
          <div className="mg-over">
            {screen === "howto" && (
              <div className="mg-card">
                <h3>{t("mg.howto_title")}</h3>
                <ul>
                  <li>{t("mg.howto_move")}</li>
                  <li>{t("mg.howto_eat")}</li>
                  <li>{t("mg.howto_combo")}</li>
                  <li>{t("mg.howto_dash")}</li>
                </ul>
                <button type="button" className="btn btn-primary btn-sm" onClick={closeHowto} autoFocus>
                  {t("mg.got_it")}
                </button>
              </div>
            )}
            {screen === "start" && (
              <div className="mg-card">
                <h3>{t("mg.title")}</h3>
                <p className="mg-sub">{t("mg.tagline")}</p>
                {best > 0 && (
                  <p className="mg-sub">
                    {t("mg.best")}: <b className="mono">{num(best)}</b>
                    {(stats?.today_best ?? 0) > 0 && (
                      <>
                        {" · "}
                        {t("mg.today")}: <b className="mono">{num(stats!.today_best)}</b>
                      </>
                    )}
                  </p>
                )}
                <div className="mg-row">
                  <button type="button" className="btn btn-primary btn-sm" onClick={begin}>
                    <Icon name="play" size={13} /> {t("mg.start")}
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setScreen("skins")}>
                    {t("mg.skins")}
                  </button>
                </div>
              </div>
            )}
            {screen === "paused" && (
              <div className="mg-card">
                <h3>{t("mg.paused")}</h3>
                <div className="mg-row">
                  <button type="button" className="btn btn-primary btn-sm" onClick={resume} autoFocus={!ready}>
                    <Icon name="play" size={13} /> {t("mg.resume")}
                  </button>
                  <button type="button" className="btn btn-sm" onClick={begin}>
                    {t("mg.restart")}
                  </button>
                </div>
              </div>
            )}
            {screen === "over" && (
              <div className="mg-card">
                <h3>{t("mg.over")}</h3>
                <p className="mg-big mono">{num(result?.score ?? hud.score)}</p>
                {(result?.new_best || result?.new_today) && (
                  <p className="mg-badge">{result.new_best ? t("mg.new_best") : t("mg.new_today")}</p>
                )}
                <p className="mg-sub">
                  {t("mg.best")}: <b className="mono">{num(best)}</b> · {t("mg.today")}: <b className="mono">{num(stats?.today_best ?? 0)}</b>
                </p>
                {result?.new_skins.map((s) => (
                  <p key={s} className="mg-badge">
                    {t("mg.unlocked", { name: skinName(s) })}
                  </p>
                ))}
                <div className="mg-row">
                  <button type="button" className="btn btn-primary btn-sm" onClick={begin} autoFocus>
                    <Icon name="refresh" size={13} /> {t("mg.again")}
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setScreen("skins")}>
                    {t("mg.skins")}
                  </button>
                </div>
              </div>
            )}
            {screen === "skins" && (
              <div className="mg-card mg-skins">
                <h3>{t("mg.skins")}</h3>
                <ul>
                  {(stats?.skins ?? [{ id: "classic", rule: "free", need: 0, have: 0, unlocked: true }]).map((s) => (
                    <li key={s.id}>
                      <SkinPreview id={s.id} locked={!s.unlocked} />
                      <span className="mg-skin-txt">
                        <b>{skinName(s.id)}</b>
                        {!s.unlocked && <span className="mg-sub">{rule(s)}</span>}
                      </span>
                      {s.unlocked ? (
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={stats?.skin === s.id}
                          aria-pressed={stats?.skin === s.id}
                          onClick={() => savePrefs({ skin: s.id })}
                        >
                          {stats?.skin === s.id ? t("mg.wearing") : t("mg.wear")}
                        </button>
                      ) : (
                        <span className="mg-locked">
                          <Icon name="lock" size={13} /> {t("mg.locked")}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="mg-sub">{t("mg.stats", { rounds: num(stats?.rounds ?? 0), fish: num(stats?.fish ?? 0) })}</p>
                <button type="button" className="btn btn-sm" onClick={() => setScreen(g.phase === "playing" ? "paused" : "start")} autoFocus>
                  {t("common.back")}
                </button>
              </div>
            )}
          </div>
        )}
        {ready && open && (
          <div className="mg-toast" role="alert">
            <b>{ready.ok ? t("mg.ready") : t("mg.failed")}</b>
            <div className="mg-row">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                autoFocus
                onClick={() => {
                  onReadySeen();
                  onClose();
                  go(href.project(ready.projectId));
                }}
              >
                {ready.ok ? t("mg.ready_open") : t("mg.failed_open")}
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  onReadySeen();
                  if (g.phase === "playing") resume();
                }}
              >
                {t("mg.keep")}
              </button>
            </div>
          </div>
        )}
      </div>
      <p className="mg-keys" id="mg-keys">
        {t("mg.hint_keys")}
      </p>
      <span className="sr-only" role="status" aria-live="polite">
        {announce}
      </span>
    </section>
  );
}

let previewGame: Game | null = null;

function SkinPreview({ id, locked }: { id: string; locked: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    previewGame ??= createGame(7);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    drawPreview(ctx, previewGame, SKINS[id] ?? SKINS.classic, c.width);
  }, [id]);
  return <canvas ref={ref} width={96} height={60} className={`mg-skin-pic${locked ? " locked" : ""}`} aria-hidden="true" />;
}
