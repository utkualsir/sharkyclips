import { useEffect, useMemo, useRef, type RefObject } from "react";
import { urls, type BrandPreset, type Candidate, type ClipOptions, type Facecam, type Word } from "../api";
import { captionAt, groupWords, joinerFor, upper } from "../captions";
import { coverRect, OUT_W, SPLIT_TOP as OUT_SPLIT, splitRects, zoomRect, zoomsAt, type PreviewFx, type Rect } from "../previewMath";

// Canvas size (9:16). The picture is cut and zoomed with previewMath.ts = what the renderer
// does (backend/sharkyclips/clips.py at 1080x1920); captions / hook / brand are drawn on top.
const W = 360;
const H = 640;
const S = W / OUT_W; // scale from the 1080-wide render to this canvas
const SPLIT_TOP = OUT_SPLIT * S;
const GOLD = "#D9B56A";

interface Props {
  video: RefObject<HTMLVideoElement>;
  clip: Candidate | null;
  /** the clip's (edited) start / end */
  range?: { start: number; end: number } | null;
  options: ClipOptions;
  facecam: Facecam | null;
  words: Word[];
  lang: string | null;
  hookText: string;
  /** smart zoom + meme shake / punch from the render plan (null: none) */
  fx?: PreviewFx | null;
  brand?: BrandPreset | null;
}

export function resolveLayout(layout: ClipOptions["layout"], facecam: Facecam | null) {
  if (layout === "auto") return facecam ? "split" : "fit";
  if (layout === "split" && !facecam) return "fit";
  return layout;
}

function blit(ctx: CanvasRenderingContext2D, v: CanvasImageSource, r: Rect, dx: number, dy: number, dw: number, dh: number) {
  if (r[2] > 0 && r[3] > 0) ctx.drawImage(v, r[0], r[1], r[2], r[3], dx, dy, dw, dh);
}

export default function VerticalPreview({ video, clip, range, options, facecam, words, lang, hookText, fx, brand }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const tiny = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 27;
    c.height = 48;
    return c;
  }, []);
  const groups = useMemo(
    () => (options.subtitles === "none" ? [] : groupWords(words, options.subtitles, lang)),
    [words, options.subtitles, lang],
  );
  const logo = useMemo(() => {
    if (!brand?.logo) return null;
    const img = new Image();
    img.src = urls.brandLogo(brand.id, brand.rev);
    return img;
  }, [brand?.id, brand?.logo, brand?.rev]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const cv = canvas.current;
    const v = video.current;
    if (!cv || !v) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = W * dpr;
    cv.height = H * dpr;
    const ctx = cv.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const layout = resolveLayout(options.layout, facecam);
    const start = range?.start ?? clip?.start ?? 0;
    const end = range?.end ?? clip?.end ?? 0;
    const prim = brand?.caption_color || "#fff";
    const high = brand?.caption_highlight || GOLD;
    const outline = brand?.caption_outline || "#000";
    const fontFam = `${brand?.caption_font ? `"${brand.caption_font}", ` : ""}Geist, Arial, "Noto Sans Arabic", "Microsoft YaHei", sans-serif`;
    let raf = 0;

    const draw = () => {
      ctx.fillStyle = "#05080f";
      ctx.fillRect(0, 0, W, H);
      const vw = v.videoWidth;
      const vh = v.videoHeight;
      const t = v.currentTime;
      const inClip = !!clip && t >= start - 0.05 && t <= end + 0.05;
      // zoom factors, all from scratch for this frame (nothing carries over between frames or clips)
      const z = zoomsAt(t, inClip ? fx ?? null : null);
      if (v.readyState >= 2 && vw && vh) {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        ctx.save();
        if (z.shake.z > 1.0001) {
          // meme shake / punch: the renderer zooms the whole picture (not the captions)
          const k = z.shake.z;
          const left = (0.5 - 0.5 / k + z.shake.dx) * W;
          const top = (0.5 - 0.5 / k + z.shake.dy) * H;
          ctx.setTransform(dpr * k, 0, 0, dpr * k, -left * dpr * k, -top * dpr * k);
        }
        const whole: Rect = [0, 0, vw, vh];
        if (layout === "crop") {
          blit(ctx, v, zoomRect(coverRect(whole, W, H), z.full), 0, 0, W, H);
        } else if (layout === "fit") {
          const tc = tiny.getContext("2d")!;
          blit(tc, v, coverRect(whole, tiny.width, tiny.height), 0, 0, tiny.width, tiny.height);
          ctx.drawImage(tiny, 0, 0, W, H);
          ctx.fillStyle = "rgba(0,0,0,0.25)";
          ctx.fillRect(0, 0, W, H);
          const scale = Math.min(W / vw, H / vh);
          const dw = vw * scale;
          const dh = vh * scale;
          blit(ctx, v, zoomRect(whole, z.full), (W - dw) / 2, (H - dh) / 2, dw, dh);
        } else if (facecam) {
          // the renderer's exact crops (clips.split_rects): the cam rect is scaled to the panel,
          // the gameplay rect center-cropped to it, then each zoomed around its focus point
          const { cam, game } = splitRects(vw, vh, facecam);
          const bottomH = H - SPLIT_TOP;
          blit(ctx, v, zoomRect(cam, z.cam, 0.45), 0, 0, W, SPLIT_TOP);
          blit(ctx, v, zoomRect(coverRect(game, W, bottomH), z.scene), 0, SPLIT_TOP, W, bottomH);
        }
        ctx.restore();
      }

      if (inClip && clip) {
        // captions
        const cap = options.subtitles === "none" ? null : captionAt(groups, t, end);
        if (cap) {
          const capY = layout === "split" ? SPLIT_TOP : 1390 * S;
          const bold = options.subtitles === "bold";
          const size = (bold ? 86 : options.subtitles === "clean" ? 62 : 56) * S;
          ctx.font = `${options.subtitles === "minimal" ? 500 : 800} ${size}px ${fontFam}`;
          ctx.textBaseline = "middle";
          ctx.direction = lang === "ar" ? "rtl" : "ltr";
          ctx.textAlign = "center";
          const texts = cap.words.map((w) => (bold ? upper(w, lang) : w));
          const joiner = joinerFor(lang);
          const full = texts.join(joiner);
          const fw = ctx.measureText(full).width;
          if (options.subtitles === "clean") {
            ctx.fillStyle = "rgba(0,0,0,0.69)";
            const padX = 14 * S * 1.4;
            const padY = 14 * S;
            ctx.beginPath();
            ctx.roundRect(W / 2 - fw / 2 - padX, capY - size / 2 - padY, fw + padX * 2, size + padY * 2, 6);
            ctx.fill();
            ctx.fillStyle = prim;
            ctx.fillText(full, W / 2, capY);
          } else if (bold && lang !== "ar") {
            // word by word so the spoken word can be highlighted
            ctx.textAlign = "left";
            let x = W / 2 - fw / 2;
            ctx.lineJoin = "round";
            ctx.lineWidth = 7 * S * 2;
            texts.forEach((w, i) => {
              const piece = i < texts.length - 1 ? w + joiner : w;
              ctx.strokeStyle = outline;
              ctx.strokeText(w, x, capY);
              ctx.fillStyle = i === cap.active ? high : prim;
              ctx.fillText(w, x, capY);
              x += ctx.measureText(piece).width;
            });
          } else {
            ctx.lineJoin = "round";
            ctx.lineWidth = (bold ? 7 : 2) * S * 2;
            ctx.strokeStyle = bold ? outline : "rgba(0,0,0,0.6)";
            ctx.strokeText(full, W / 2, capY);
            ctx.fillStyle = prim;
            ctx.fillText(full, W / 2, capY);
          }
        }
        // hook
        // (a seamless loop shows it for the last moment too: it is already there when the clip starts over)
        if (options.hook && hookText && (t - start < 3.2 || (options.loop && t <= end && end - t < 0.8))) {
          const hookY = (layout === "fit" ? 330 : 120) * S;
          const size = 64 * S;
          ctx.font = `800 ${size}px ${fontFam}`;
          ctx.direction = lang === "ar" ? "rtl" : "ltr";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          // wrap to max width
          const maxW = W - 2 * 90 * S - 2 * 22 * S;
          const lines: string[] = [];
          let line = "";
          for (const word of hookText.split(/\s+/)) {
            const test = line ? `${line} ${word}` : word;
            if (ctx.measureText(test).width > maxW && line) {
              lines.push(line);
              line = word;
            } else line = test;
          }
          if (line) lines.push(line);
          const lh = size * 1.18;
          const pad = 22 * S;
          ctx.fillStyle = "#fff";
          lines.forEach((l, i) => {
            const lw = ctx.measureText(l).width;
            ctx.fillRect(W / 2 - lw / 2 - pad, hookY + i * lh - pad / 2, lw + pad * 2, lh + pad);
          });
          ctx.fillStyle = "#0E1A33";
          lines.forEach((l, i) => ctx.fillText(l, W / 2, hookY + i * lh + (lh - size) / 2));
        }
      }

      // brand kit: logo watermark + @handle (same placement as the renderer)
      if (brand) {
        const m = 40 * S;
        const right = brand.logo_pos === "tr" || brand.logo_pos === "br";
        const top = brand.logo_pos === "tl" || brand.logo_pos === "tr";
        let lh = 0;
        if (logo && logo.complete && logo.naturalWidth) {
          const lw = (W * brand.logo_size) / 100;
          lh = (lw * logo.naturalHeight) / logo.naturalWidth;
          ctx.globalAlpha = brand.logo_opacity;
          ctx.drawImage(logo, right ? W - lw - m : m, top ? m : H - lh - m, lw, lh);
          ctx.globalAlpha = 1;
        }
        if (brand.handle && brand.show_handle) {
          ctx.font = `800 ${38 * S}px ${fontFam}`;
          ctx.textAlign = right ? "right" : "left";
          ctx.textBaseline = top ? "top" : "bottom";
          ctx.direction = "ltr";
          const y = top ? m + lh + (lh ? 10 * S : 0) : H - m - lh - (lh ? 10 * S : 0);
          ctx.lineWidth = 3 * S * 2;
          ctx.strokeStyle = "rgba(0,0,0,0.6)";
          ctx.strokeText(`@${brand.handle}`, right ? W - m : m, y);
          ctx.fillStyle = "#fff";
          ctx.fillText(`@${brand.handle}`, right ? W - m : m, y);
        }
      }
    };

    const loop = () => {
      draw();
      if (!v.paused && !v.ended) raf = requestAnimationFrame(loop);
    };
    const kick = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(loop);
    };
    const events = ["play", "seeked", "loadeddata", "timeupdate", "pause"];
    events.forEach((e) => v.addEventListener(e, kick));
    logo?.addEventListener("load", kick);
    kick();
    return () => {
      cancelAnimationFrame(raf);
      events.forEach((e) => v.removeEventListener(e, kick));
      logo?.removeEventListener("load", kick);
    };
  }, [video, clip, range?.start, range?.end, options, facecam, groups, lang, hookText, tiny, fx, brand, logo]); // eslint-disable-line react-hooks/exhaustive-deps

  return <canvas ref={canvas} width={W} height={H} aria-hidden="true" />;
}
