"use client";
import { createContext, useContext, useState } from "react";
type Locale = "en" | "zh-Hant";
const LocaleContext = createContext({
  locale: "en" as Locale,
  t: (en: string, zh: string) => en,
  toggle: () => {},
});
export function LocaleProvider({
  initial,
  children,
}: {
  initial: Locale;
  children: React.ReactNode;
}) {
  const [locale, setLocale] = useState<Locale>(initial);
  function toggle() {
    const next = locale === "en" ? "zh-Hant" : "en";
    setLocale(next);
    document.cookie = `cp_locale=${next}; Path=/; SameSite=Lax; Max-Age=31536000`;
    document.documentElement.lang = next;
  }
  return (
    <LocaleContext
      value={{ locale, t: (en, zh) => (locale === "en" ? en : zh), toggle }}
    >
      {children}
    </LocaleContext>
  );
}
export const useLocale = () => useContext(LocaleContext);
export function LocaleSwitch() {
  const { locale, toggle } = useLocale();
  return (
    <button
      className="quiet"
      onClick={toggle}
      lang={locale === "en" ? "zh-Hant" : "en"}
    >
      {locale === "en" ? "繁體中文" : "English"}
    </button>
  );
}
