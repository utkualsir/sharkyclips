// The colours the renderer burns into the 9:16 video (captions, hook box, handle, letterbox).
// The live preview draws with these so it looks exactly like the export (preview = export): they
// never follow the app's theme. Defaults of backend/sharkyclips/captions.py / clips.py.
export const EXPORT = {
  caption: "#ffffff",
  highlight: "#D9B56A",
  outline: "#000000",
  canvas: "#05080f",
  fitDim: "rgba(0,0,0,0.25)",
  cleanBox: "rgba(0,0,0,0.69)",
  thinOutline: "rgba(0,0,0,0.6)",
  hookBox: "#ffffff",
  hookText: "#0E1A33",
  handle: "#ffffff",
} as const;
