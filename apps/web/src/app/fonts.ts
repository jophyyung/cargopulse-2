import localFont from "next/font/local";

// Hanken Grotesk and Instrument Serif (SIL Open Font License, see src/fonts/OFL-*.txt)
// are bundled as local files: the Content-Security-Policy allows no external fonts.
export const hanken = localFont({
  src: [{ path: "../fonts/hanken-grotesk-latin-wght-normal.woff2", weight: "100 900", style: "normal" }],
  variable: "--font-hanken",
  display: "swap",
  fallback: ["Segoe UI", "Arial"],
});

// Page titles and hero lines only (28 px and up).
export const instrumentSerif = localFont({
  src: [{ path: "../fonts/instrument-serif-latin-400-normal.woff2", weight: "400", style: "normal" }],
  variable: "--font-instrument",
  display: "swap",
  fallback: ["Georgia", "Times New Roman"],
});
