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
import {
  BookOpen, Cable, FileCheck2, Lock, LogOut, Scale, ScrollText, TowerControl, UserRound,
} from "lucide-react";
import { LocaleSwitch, useLocale } from "./locale";
import { BrandMark } from "./kit/brand-mark";
import { FlapNumber } from "./kit/flap-number";
import { UldIcon } from "./kit/uld-icon";
const navigation = [
  ["/operations", "Recovery desk", "復原作業台", TowerControl],
  ["/protect", "Protect sandbox", "Protect 沙盒", UldIcon],
  ["/evidence", "Evidence", "證據", FileCheck2],
  ["/policies", "Policies", "政策", Scale],
  ["/integrations", "Integrations", "整合", Cable],
  ["/audit", "Audit trail", "稽核紀錄", ScrollText],
  ["/help", "Operator guide", "操作指引", BookOpen],
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
        <div className="service-error-top">
          <p className="brand">
            <BrandMark />
            CargoPulse
          </p>
          <LocaleSwitch />
        </div>
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
        {phase === "hidden" ? <div className="actions">
          <a className="button primary" href="/login">{t("Sign in again", "重新登入")}</a>
          {outcome !== "confirmed" ? <button className="button" disabled={outcome === "pending"} onClick={logout}>
            {t("Retry sign out", "重試登出")}
          </button> : null}
        </div> : null}
        <p className="placard">SYNTHETIC / NOT CONNECTED</p>
      </main>
    );
  }
  return (
    <div className="app" data-testid="private-console">
      <a className="skip" href="#main">
        {t("Skip to content", "跳至主要內容")}
      </a>
      <aside className="rail">
        <Link href="/operations" className="rail-brand" aria-label="CargoPulse">
          <BrandMark />
        </Link>
        <nav aria-label={t("Main navigation", "主要導覽")}>
          {navigation.map(([href, en, zh, Icon]) => (
            <Link
              key={href}
              href={href}
              className="rail-link"
              aria-current={pathname.startsWith(href) ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
              <span>{t(en, zh)}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <p className="wordmark">CargoPulse</p>
          <div className="tenant">
            <span>{t("Tenant", "租戶")}</span>
            <code title={user.tenant_id}>{user.tenant_id}</code>
          </div>
          <p className="placard">SYNTHETIC / NOT CONNECTED</p>
          <HubClock />
          <LocaleSwitch />
          <div className="account">
            <UserRound size={18} strokeWidth={1.75} aria-hidden="true" />
            <span>
              <strong>{user.roles.map(roleName).join(", ")}</strong>
              <small>
                {user.auth_mode === "development"
                  ? t("Development identity", "開發身分")
                  : "OIDC"}
                {", "}
                {user.subject}
              </small>
            </span>
          </div>
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
            <LogOut size={16} strokeWidth={1.75} aria-hidden="true" />
            {t("Sign out", "登出")}
          </button>
        </header>
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <footer className="boundary">
          <p>
            <Lock size={14} strokeWidth={2} aria-hidden="true" />
            {t("External writes disabled", "外部寫入已停用")}
          </p>
          <p>
            {t(
              "Decision support. Human authority.",
              "決策支援。由人員掌握決策權。",
            )}
          </p>
          <p>
            {t(
              "Proposals and decisions remain inside CargoPulse.",
              "建議方案及決策僅記錄於 CargoPulse。",
            )}
          </p>
          <nav aria-label={t("Notices", "聲明")}>
            <Link href="/privacy">{t("Privacy", "私隱")}</Link>
            <Link href="/terms">{t("Terms", "使用條款")}</Link>
          </nav>
        </footer>
      </div>
    </div>
  );
}
/** "data_steward" → "Data steward". Role identifiers come from the service. */
function roleName(role: string) {
  const words = role.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
const hktTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Hong_Kong", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const utcTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
/** The device clock, shown in Hong Kong time and UTC. Tiles flip when a minute passes. */
function HubClock() {
  const { t } = useLocale();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  const hkt = now ? hktTime.format(now) : null;
  const utc = now ? utcTime.format(now) : null;
  return (
    <div className="hub-clock" role="group" aria-label={t("Current time", "目前時間")}>
      <span>
        <abbr title={t("Hong Kong Time", "香港時間")}>HKT</abbr>
        <FlapNumber value={hkt} minLength={5} size="sm" label={hkt ?? ""} />
      </span>
      <span>
        <abbr title={t("Coordinated Universal Time", "協調世界時")}>UTC</abbr>
        <FlapNumber value={utc} minLength={5} size="sm" label={utc ?? ""} />
      </span>
    </div>
  );
}
