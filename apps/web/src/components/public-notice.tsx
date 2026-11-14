"use client";

import Link from "next/link";
import { LocaleSwitch, useLocale } from "./locale";

export function PublicNotice({ children }: { children: React.ReactNode }) {
  const { t } = useLocale();
  return (
    <div className="public-notice">
      <a className="skip" href="#main">{t("Skip to content", "跳至主要內容")}</a>
      <header>
        <Link className="brand" href="/login">CargoPulse</Link>
        <LocaleSwitch />
      </header>
      <p className="eyebrow">SYNTHETIC / NOT CONNECTED</p>
      <main id="main" tabIndex={-1}>{children}</main>
      <footer>
        <Link href="/login">{t("Back to sign-in", "返回登入")}</Link>
        <span>{t("Evaluation notices · external release pending review", "評估聲明 · 對外發布尚待審閱")}</span>
      </footer>
    </div>
  );
}
