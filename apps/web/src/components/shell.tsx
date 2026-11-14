"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { flushSync } from "react-dom";
import type { Principal } from "@/lib/types";
import { api } from "@/lib/api";
import {
  hideSession, verifyWorkspaceSession,
  SESSION_BOUNDARY_EVENT, SESSION_BOUNDARY_KEY, type BoundaryReason,
} from "@/lib/session-boundary";
import { LocaleSwitch, useLocale } from "./locale";
const navigation = [
  ["/operations", "Recovery desk", "復原作業台", "01"],
  ["/protect", "Protect sandbox", "Protect 沙盒", "02"],
  ["/evidence", "Evidence", "證據", "03"],
  ["/policies", "Policies", "政策", "04"],
  ["/integrations", "Integrations", "整合", "05"],
  ["/audit", "Audit trail", "稽核紀錄", "06"],
  ["/help", "Operator guide", "操作指引", "07"],
] as const;
export function Shell({
  user,
  children,
}: {
  user: Principal;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { t } = useLocale();
  const [phase, setPhase] = useState<"checking" | "ready" | "hidden">("checking");
  const [reason, setReason] = useState<BoundaryReason>("signin");
  const [outcome, setOutcome] = useState<"pending" | "confirmed" | "unconfirmed">("unconfirmed");
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    let hidden = false;
    let checking = false;
    let expiryTimer: ReturnType<typeof setTimeout> | undefined;
    function redact(next: BoundaryReason) {
      hidden = true;
      clearTimeout(expiryTimer);
      // A logout/offline/401 event removes the subtree before subsequent work.
      flushSync(() => { setReason(next); setPhase("hidden"); });
    }
    function onHidden(event: Event) { redact((event as CustomEvent<BoundaryReason>).detail); }
    function onStorage(event: StorageEvent) {
      if (event.key !== SESSION_BOUNDARY_KEY && event.key !== null) return;
      try {
        // A later sign-in may already have overwritten storage before an older
        // logout notification is delivered. Honor the queued event itself.
        const change = event.newValue ? JSON.parse(event.newValue) : null;
        if (!change || change.v !== 1 || change.state !== 0) redact("other-tab");
      } catch { redact("unavailable"); }
    }
    function offline() { hideSession("offline"); }
    function pageTransition(event: PageTransitionEvent) {
      if (event.persisted) hideSession("return");
    }
    async function verify() {
      // Start outside the effect lifecycle so synchronous event redaction is safe.
      await Promise.resolve();
      if (disposed || hidden || checking || document.visibilityState === "hidden") return;
      checking = true;
      try {
        const verified = await verifyWorkspaceSession(
          AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]),
        );
        if (disposed || hidden) return;
        if (verified !== null) {
          const remaining = verified - performance.now();
          if (remaining <= 0) { hideSession("expired"); return; }
          clearTimeout(expiryTimer);
          expiryTimer = setTimeout(() => hideSession("expired"), remaining);
          setPhase("ready");
        } else redact("signin");
      } catch {
        if (!disposed) hideSession("unavailable");
      } finally { checking = false; }
    }
    window.addEventListener(SESSION_BOUNDARY_EVENT, onHidden);
    window.addEventListener("storage", onStorage);
    window.addEventListener("offline", offline);
    window.addEventListener("pagehide", pageTransition);
    window.addEventListener("pageshow", pageTransition);
    window.addEventListener("focus", verify);
    document.addEventListener("visibilitychange", verify);
    void verify();
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(expiryTimer);
      window.removeEventListener(SESSION_BOUNDARY_EVENT, onHidden);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("offline", offline);
      window.removeEventListener("pagehide", pageTransition);
      window.removeEventListener("pageshow", pageTransition);
      window.removeEventListener("focus", verify);
      document.removeEventListener("visibilitychange", verify);
    };
  }, []);
  async function logout() {
    setOutcome("pending");
    hideSession("logout");
    try {
      const result = await api<{ revoked: boolean }>("/auth/logout", { method: "POST" });
      if (result.revoked !== true) throw new Error("Sign-out was not confirmed");
      setOutcome("confirmed");
    } catch {
      setOutcome("unconfirmed");
    }
  }
  if (phase !== "ready") {
    return (
      <main className="service-error" data-testid="session-boundary">
        <LocaleSwitch />
        <p className="eyebrow">CargoPulse</p>
        <h1>{phase === "checking"
          ? t("Verifying your session…", "正在驗證您的登入……")
          : outcome === "confirmed" ? t("Signed out", "已登出")
            : t("Private workspace hidden", "私人工作區已隱藏")}</h1>
        <p role="status">{phase === "checking"
          ? t("Private records will appear after verification.", "驗證完成後才會顯示私人紀錄。")
          : outcome === "confirmed"
            ? t("The service confirmed sign-out. Sign in again to continue.", "服務已確認登出。請重新登入以繼續。")
            : outcome === "pending"
              ? t("Private records are no longer displayed. Waiting for sign-out confirmation.", "私人紀錄已停止顯示。正在等候登出確認。")
              : reason === "expired"
                ? t("Your session needs to be verified again. Sign in again to continue.", "需要再次驗證您的登入。請重新登入以繼續。")
                : reason === "offline"
                  ? t("You are offline. Server sign-out is not confirmed. Reconnect and sign in again.", "您目前離線。尚未確認伺服器登出，請重新連線後登入。")
                  : t("Server sign-out is not confirmed. Sign in again before opening private records.", "尚未確認伺服器登出。請先重新登入，才再次開啟私人紀錄。")}</p>
        {phase === "hidden" ? <>
          <a className="button primary" href="/login">{t("Sign in again", "重新登入")}</a>
          {outcome !== "confirmed" ? <button className="quiet" disabled={outcome === "pending"} onClick={logout}>
            {t("Retry sign out", "重試登出")}
          </button> : null}
        </> : null}
        <p>SYNTHETIC / NOT CONNECTED</p>
      </main>
    );
  }
  return (
    <div className="app" data-testid="private-console">
      <a className="skip" href="#main">
        {t("Skip to content", "跳至主要內容")}
      </a>
      <aside className="sidebar">
        <Link href="/operations" className="brand">
          <span className="brand-symbol" aria-hidden="true">
            C<span>↗</span>
          </span>
          <span>
            CargoPulse<small>{t("OPERATIONS WORKSPACE", "作業工作區")}</small>
          </span>
        </Link>
        <p className="nav-label">{t("WORKSPACE", "工作區")}</p>
        <nav aria-label={t("Main navigation", "主要導覽")}>
          {navigation.map(([href, en, zh, n]) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname.startsWith(href) ? "page" : undefined}
            >
              <span>{n}</span>
              {t(en, zh)}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="nav-label">{t("OPERATING BOUNDARY", "作業範圍")}</p>
          <p>
            {t(
              "Decision support. Human authority.",
              "決策支援。由人員掌握決策權。",
            )}
          </p>
          <span className="badge">
            {t("EXTERNAL WRITES DISABLED", "外部寫入已停用")}
          </span>
          <Link href="/protect" className="muted-link">
            {t("Protect · synthetic sandbox", "Protect · 合成沙盒")}
          </Link>
        </div>
      </aside>
      <div className="workspace">
        <div className="topbar">
          <div className="tenant">
            <span className="tenant-dot" aria-hidden="true" />
            <div>
              <strong>{t("Tenant workspace", "租戶工作區")}</strong>
              <code>{user.tenant_id}</code>
            </div>
          </div>
          <div className="account">
            <LocaleSwitch />
            <span>
              {user.roles.join(" · ")}
              <small>
                {user.auth_mode === "development"
                  ? t("DEVELOPMENT IDENTITY", "開發身分")
                  : "OIDC"}{" "}
                · {user.subject}
              </small>
            </span>
            {user.auth_mode === "development" ? (
              <button
                className="quiet"
                onClick={() => {
                  hideSession("signin");
                  window.location.assign(`/login?switch=1&next=${encodeURIComponent(pathname + location.search)}`);
                }}
              >
                {t("Switch role", "切換角色")}
              </button>
            ) : null}
            <button className="quiet" onClick={logout}>
              {t("Sign out", "登出")}
            </button>
          </div>
        </div>
        <div className="evidence-strip">
          <span>SYNTHETIC / NOT CONNECTED</span>
          <span>
            {t(
              "Proposals and decisions remain inside CargoPulse.",
              "建議方案及決策僅記錄於 CargoPulse。",
            )}
          </span>
        </div>
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <footer>
          <span>
            CargoPulse ·{" "}
            {t("Synthetic recovery evaluation", "合成資料復原評估")}
          </span>
          <div>
            <Link href="/privacy">{t("Privacy", "私隱")}</Link>
            <Link href="/terms">{t("Terms", "使用條款")}</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
