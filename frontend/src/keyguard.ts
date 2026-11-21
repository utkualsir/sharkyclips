// 1.2.59: keyboard isolation for the waiting mini game.
//
// The app has single-key shortcuts (A / X / Space / J / K / L / ? ...) on window listeners. While
// focus is inside the game panel ([data-game-root]) its keys must never reach them, and the game
// must never hear keys typed elsewhere. This listener is added first (main.tsx, before React), on
// window in the capture phase, so it runs before every other key listener: keys from inside the
// panel go to the game's handler only and stop there; everything else passes untouched.
// Default actions are kept (Tab still moves focus, Enter / Space still press a focused button).

type Handler = (e: KeyboardEvent) => void;
let handler: Handler | null = null;
let installed = false;

export const GAME_ROOT_ATTR = "data-game-root";

export function setGameKeyHandler(h: Handler | null): void {
  handler = h;
}

function insideGame(e: KeyboardEvent): boolean {
  const t = e.target;
  return t instanceof Element && !!t.closest(`[${GAME_ROOT_ATTR}]`);
}

function guard(e: KeyboardEvent): void {
  if (!insideGame(e)) return;
  e.stopImmediatePropagation();
  if (e.type !== "keypress") handler?.(e);
}

export function installKeyGuard(): void {
  if (installed) return;
  installed = true;
  for (const type of ["keydown", "keyup", "keypress"] as const) window.addEventListener(type, guard, true);
}
