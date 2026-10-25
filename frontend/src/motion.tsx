import { useEffect, useRef, useState } from "react";

// Animation level: the Settings choice (Full / Reduced / Off), capped by the OS "reduce motion"
// setting. The effective level sits on <html data-motion="..."> (index.html sets it before the
// first paint from localStorage), so CSS and JS read the same value.
export type MotionSetting = "full" | "reduced" | "off";
const KEY = "sc-motion";

function osReduced(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export function storedMotion(): MotionSetting {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "full" || v === "reduced" || v === "off") return v;
  } catch {
    /* private mode */
  }
  return "full";
}

export function effective(setting: MotionSetting = storedMotion()): MotionSetting {
  if (setting === "off") return "off";
  return setting === "reduced" || osReduced() ? "reduced" : "full";
}

export function applyMotion(setting: MotionSetting) {
  try {
    localStorage.setItem(KEY, setting);
  } catch {
    /* ignore */
  }
  document.documentElement.setAttribute("data-motion", effective(setting));
  window.dispatchEvent(new CustomEvent("sc-motion"));
}

/** Current effective level; follows the setting and the OS preference. */
export function motion(): MotionSetting {
  const v = document.documentElement.getAttribute("data-motion");
  return v === "reduced" || v === "off" ? v : "full";
}

export function useMotion(): MotionSetting {
  const [m, setM] = useState(motion);
  useEffect(() => {
    const on = () => setM(motion());
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const onOs = () => applyMotion(storedMotion());
    window.addEventListener("sc-motion", on);
    mq?.addEventListener?.("change", onOs);
    return () => {
      window.removeEventListener("sc-motion", on);
      mq?.removeEventListener?.("change", onOs);
    };
  }, []);
  return m;
}

const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);

/** 0 -> 1 over `ms` once `key` changes (Hype Map bars growing in). 1 right away without motion. */
export function useTween(key: unknown, ms = 700): number {
  const [v, setV] = useState(() => (motion() === "full" ? 0 : 1));
  useEffect(() => {
    if (motion() !== "full") {
      setV(1);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    setV(0);
    const step = (now: number) => {
      const x = Math.min(1, (now - t0) / ms);
      setV(x);
      if (x < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [key, ms]);
  return v;
}

/** A number that counts up to `target` (from 0 the first time, then from the old value). */
export function useCountUp(target: number | null | undefined, ms = 650): number | null {
  const [val, setVal] = useState<number | null>(() =>
    target == null ? null : motion() === "full" ? 0 : target,
  );
  const from = useRef(0);
  useEffect(() => {
    if (target == null) {
      setVal(null);
      return;
    }
    if (motion() !== "full") {
      setVal(target);
      from.current = target;
      return;
    }
    const start = from.current;
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const x = Math.min(1, (now - t0) / ms);
      const v = start + (target - start) * easeOut(x);
      setVal(x < 1 ? v : target);
      if (x < 1) raf = requestAnimationFrame(step);
      else from.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      from.current = target;
    };
  }, [target, ms]);
  return val;
}

export function CountUp({ value, format }: { value: number; format?: (n: number) => string }) {
  const v = useCountUp(value) ?? value;
  const n = Math.round(v);
  return <>{format ? format(n) : n}</>;
}
