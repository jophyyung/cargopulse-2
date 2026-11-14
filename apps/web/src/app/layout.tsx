import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import "@fontsource-variable/noto-sans-tc/wght.css";
import { Graticule } from "@/components/chart/graticule";
import { LocaleProvider } from "@/components/locale";
import { barlow, barlowCondensed } from "./fonts";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "CargoPulse | Recovery operations",
    template: "%s | CargoPulse",
  },
  description:
    "Synthetic air cargo recovery decision workspace. Not connected to airline systems.",
};
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await headers();
  const locale =
    (await cookies()).get("cp_locale")?.value === "zh-Hant" ? "zh-Hant" : "en";
  return (
    <html lang={locale} className={`${barlow.variable} ${barlowCondensed.variable}`}>
      <body>
        <Graticule />
        <LocaleProvider initial={locale}>{children}</LocaleProvider>
      </body>
    </html>
  );
}
