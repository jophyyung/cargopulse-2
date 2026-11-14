"use client";
import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { hideSession, confirmDevelopmentSignIn, prepareOrganisationSignIn } from "@/lib/session-boundary";
import { LocaleSwitch, useLocale } from "./locale";
import { ErrorNotice } from "./ui";
export function Login({ development }: { development: boolean }) {
  const { t } = useLocale();
  const [identity, setIdentity] = useState("controller");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function signin(event: React.FormEvent) {
    event.preventDefault();
    setError(undefined);
    setBusy(true);
    hideSession("signin");
    try {
      if (new URLSearchParams(location.search).has("switch")) {
        try { await api("/auth/logout", { method: "POST" }); }
        catch (error) {
          if (!(error instanceof ApiError) || ![401, 403].includes(error.status)) throw error;
        }
      }
      await api("/auth/development", {
        method: "POST",
        body: { identity_id: identity },
      });
      await confirmDevelopmentSignIn();
      const next = new URLSearchParams(location.search).get("next");
      window.location.replace(
        next &&
          /^\/(operations|policies|audit|evidence|plans)([/?]|$)/.test(next)
          ? next
          : "/operations",
      );
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }
  async function organisationSignin(event: React.MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    if (busy) return;
    setError(undefined);
    setBusy(true);
    try {
      await prepareOrganisationSignIn();
      window.location.assign("/api/v1/auth/login");
    } catch (error) {
      setError(error);
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <div className="login-story">
        <p className="brand">CargoPulse</p>
        <p className="eyebrow">{t("RECOVERY OPERATIONS", "復原作業")}</p>
        <h1>
          {t(
            "A clear path.\nAn accountable decision.",
            "明確路徑。\n可追溯決策。",
          )}
        </h1>
        <p>
          {t(
            "Review feasible cargo recovery proposals, inspect the evidence and record a human decision.",
            "檢視可行的貨運復原建議、核對證據，並記錄由人員作出的決策。",
          )}
        </p>
        <div className="login-boundary">
          <span>SYNTHETIC / NOT CONNECTED</span>
          <p>
            {t(
              "No airline connection. No physical dispatch or external write-back.",
              "未連接航空公司系統。不會執行實體調度或外部寫入。",
            )}
          </p>
        </div>
      </div>
      <section className="login-form">
        <LocaleSwitch />
        <p className="eyebrow">{t("SECURE WORKSPACE", "安全工作區")}</p>
        <h2>{t("Sign in to CargoPulse", "登入 CargoPulse")}</h2>
        <p>
          {t(
            "Use your provisioned organisation account. Your tenant and permissions are verified by the service.",
            "請使用已配置的機構帳戶。服務將驗證您的租戶及權限。",
          )}
        </p>
        <a className="button primary wide" href="/api/v1/auth/login" onClick={organisationSignin} aria-disabled={busy}>
          {t("Continue with organisation SSO", "使用機構 SSO 繼續")}{" "}
          <span aria-hidden="true">↗</span>
        </a>
        <ErrorNotice error={error} />
        {development ? (
          <form onSubmit={signin} className="dev-login">
            <span className="badge">{t("DEVELOPMENT ONLY", "僅供開發")}</span>
            <h3>{t("Synthetic evaluation identity", "合成資料評估身分")}</h3>
            <p>
              {t(
                "Fixed local identities; this does not verify a production SSO login. Switch to Data steward for imports and Controller for solving.",
                "固定本機身分；這並非正式 SSO 登入驗證。匯入資料時選擇 Data steward，求解時選擇 Controller。",
              )}
            </p>
            <label>
              {t("Evaluation role", "評估角色")}
              <select
                value={identity}
                onChange={(e) => setIdentity(e.target.value)}
              >
                <option value="controller">Controller</option>
                <option value="steward">Data steward</option>
                <option value="manager">Manager · author</option>
                <option value="manager-reviewer">
                  Manager · independent reviewer
                </option>
                <option value="auditor">Auditor</option>
                <option value="controller-b">
                  Controller B · second tenant
                </option>
              </select>
            </label>
            <button className="button" disabled={busy}>
              {busy
                ? t("Verifying…", "正在驗證……")
                : t("Enter evaluation workspace", "進入評估工作區")}
            </button>
          </form>
        ) : null}
        <p className="fine">
          {t(
            "Access is tenant scoped. In-app approval never authorises airline operations.",
            "存取按租戶範圍限制。應用程式內的核准不會授權航空公司作業。",
          )}
        </p>
        <p className="fine legal-links">
          <Link href="/privacy">{t("Privacy & data handling", "私隱及資料處理")}</Link>
          <span aria-hidden="true"> · </span>
          <Link href="/terms">{t("Terms of evaluation", "評估使用條款")}</Link>
        </p>
      </section>
    </main>
  );
}
