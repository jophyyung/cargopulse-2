"use client";
import Link from "next/link";
import { useLocale } from "./locale";
import { PageHeader, Section } from "./ui";
export function Information({
  kind,
}: {
  kind: "integrations" | "protect" | "help" | "privacy" | "terms";
}) {
  const { t } = useLocale();
  if (kind === "integrations")
    return (
      <>
        <PageHeader
          eyebrow={t("SYSTEM / SOURCE BOUNDARY", "系統 / 來源範圍")}
          title={t("Integrations", "整合")}
          description={t(
            "No external source is connected. Synthetic imports are the only enabled intake.",
            "未連接任何外部來源。合成資料匯入是唯一啟用的輸入方式。",
          )}
        />
        <div className="integration-grid">
          {[
            [
              "ONE Record",
              "Authorised provider scope and mapping are required.",
              "需要已授權的供應商範圍及對應設定。",
            ],
            [
              "Airline operations",
              "No credentials, live feed or write-back is configured.",
              "未配置憑證、即時資料流或寫入。",
            ],
            [
              "Operational dispatch",
              "In-app decisions cannot trigger external dispatch.",
              "應用程式內決策無法觸發外部調度。",
            ],
          ].map(([name, en, zh]) => (
            <Section key={name} title={name}>
              <span className="badge">NOT CONNECTED</span>
              <p>{t(en, zh)}</p>
              <button className="button" disabled>
                {t("Connection unavailable", "無法連接")}
              </button>
            </Section>
          ))}
        </div>
        <Link className="text-link" href="/operations">
          {t("Go to synthetic intake", "前往合成資料匯入")} →
        </Link>
      </>
    );
  if (kind === "protect")
    return (
      <>
        <PageHeader
          eyebrow="PROTECT"
          title={t(
            "Protect planner is unavailable",
            "Protect 規劃工具尚未提供",
          )}
          description={t(
            "Pre-cutoff load planning remains disabled pending its own validator and acceptance flow. No Protect performance is claimed.",
            "起飛截止前裝載規劃維持停用，等待其獨立驗證器及驗收流程。不宣稱任何 Protect 表現。",
          )}
        />
        <Section
          title={t(
            "Use Recover for evaluated incidents",
            "請使用 Recover 評估事件",
          )}
        >
          <p>
            {t(
              "Only the Recover decision workflow is enabled in this build.",
              "此版本僅啟用 Recover 決策流程。",
            )}
          </p>
          <Link className="button" href="/operations">
            {t("Open recovery desk", "開啟復原作業台")}
          </Link>
        </Section>
      </>
    );
  if (kind === "privacy")
    return (
      <>
        <PageHeader
          eyebrow={t("WORKSPACE NOTICE", "工作區聲明")}
          title={t("Privacy & data handling", "私隱及資料處理")}
          description={t(
            "Synthetic evaluation scope. Deployment-specific retention and operator contact must be configured before external release.",
            "合成資料評估範圍。對外發布前，必須配置部署專用的保留政策及營運者聯絡方式。",
          )}
        />
        <Section title={t("Data in this workspace", "本工作區資料")}>
          <p>
            {t(
              "Use synthetic cargo records only. Do not enter personal, customer-confidential or restricted operational data. Session cookies maintain authentication; the application does not store access tokens in browser local storage.",
              "只可使用合成貨運紀錄。切勿輸入個人、客戶機密或受限作業資料。工作階段 Cookie 用於維持驗證；應用程式不會將存取權杖儲存在瀏覽器本機儲存空間。",
            )}
          </p>
          <p>
            {t(
              "Imports, decisions and exports are tenant scoped. Audit records preserve actor identifiers, timestamps, resource references, outcomes and integrity hashes. Downloaded evidence is your responsibility to handle within authorised access.",
              "匯入、決策及匯出均按租戶範圍限制。稽核紀錄保留執行者識別碼、時間、資源參考、結果及完整性雜湊值。您須在授權範圍內妥善處理下載證據。",
            )}
          </p>
        </Section>
      </>
    );
  if (kind === "terms")
    return (
      <>
        <PageHeader
          eyebrow={t("EVALUATION BOUNDARY", "評估範圍")}
          title={t("Terms of evaluation", "評估使用條款")}
          description={t(
            "Decision support using synthetic conservative models. This workspace is not an airline system of record.",
            "以合成保守模型提供決策支援。本工作區並非航空公司的權威記錄系統。",
          )}
        />
        <Section title={t("Human review is required", "必須經人員審查")}>
          <p>
            {t(
              "Proposals are model outputs, not guaranteed cargo movements. Independent PASS refers to implemented synthetic gates and cannot certify aircraft balance, physical packing, regulatory compliance or dangerous-goods clearance.",
              "建議方案為模型輸出，並不保證貨物移動。獨立驗證 PASS 僅指已實作的合成條件，不能認證飛機平衡、實體裝載、法規合規或危險品許可。",
            )}
          </p>
          <p>
            {t(
              "Approve in-app records a CargoPulse decision only. No physical dispatch, booking, manifest or external system change is performed. Follow approved operating procedures for actual operations.",
              "應用程式內核准僅記錄 CargoPulse 決策。不會執行實體調度、訂艙、貨單或外部系統變更。實際作業請遵循已批准的作業程序。",
            )}
          </p>
        </Section>
      </>
    );
  return (
    <>
      <PageHeader
        eyebrow={t("OPERATOR REFERENCE", "操作參考")}
        title={t("A deliberate recovery workflow", "審慎的復原流程")}
        description={t(
          "Inspect the evidence, understand the feasible choices and keep the human decision accountable.",
          "檢視證據、了解可行選項，並確保人員決策可追溯。",
        )}
      />
      <div className="two-col">
        <Section title={t("From input to decision", "從輸入到決策")}>
          <ol className="guide-list">
            <li>
              <strong>{t("Validate source", "驗證來源")}</strong>
              <p>
                {t(
                  "A Data steward or Manager validates and commits a synthetic snapshot. Resolve blocking row errors before proceeding.",
                  "Data steward 或 Manager 驗證並提交合成快照。繼續前須解決阻擋性資料列錯誤。",
                )}
              </p>
            </li>
            <li>
              <strong>{t("Lock the scenario", "鎖定情境")}</strong>
              <p>
                {t(
                  "A Controller creates a scenario from the committed source ID. Review affected ULDs, physical quantities, evidence times and published policy.",
                  "Controller 使用已提交來源 ID 建立情境。請檢視受影響 ULD、實體數量、證據時間及已發布政策。",
                )}
              </p>
            </li>
            <li>
              <strong>{t("Compare feasible paths", "比較可行路徑")}</strong>
              <p>
                {t(
                  "Excluded arcs show hard-gate reason codes. Missing evidence is unknown, never assumed safe. Exact cutoff times define the action window.",
                  "已排除航段顯示硬性條件原因代碼。缺少證據視為未知，絕不假定安全。精確截止時間界定行動時限。",
                )}
              </p>
            </li>
            <li>
              <strong>
                {t("Solve, validate and review", "求解、驗證及檢視")}
              </strong>
              <p>
                {t(
                  "Jobs persist through navigation. Review validator status, solver termination, unassigned units, alternatives and the denominator of every metric.",
                  "工作在切換頁面後仍會保留。請檢視驗證器狀態、求解終止原因、未分配單位、替代方案及各指標分母。",
                )}
              </p>
            </li>
            <li>
              <strong>{t("Record the decision", "記錄決策")}</strong>
              <p>
                {t(
                  "Verify full hashes, enter a reason and type the action. A changed snapshot produces a conflict; refresh and review before retrying.",
                  "核對完整雜湊值、填寫理由並輸入動作名稱。快照變更會產生衝突；重試前須重新整理及審查。",
                )}
              </p>
            </li>
          </ol>
        </Section>
        <Section title={t("Interpretation & fallback", "解讀及後備處理")}>
          <dl className="glossary">
            <dt>ULD ≠ AWB</dt>
            <dd>
              {t(
                "A physical ULD may contain pieces from multiple AWBs. ULD recovery is not an AWB offload rate.",
                "實體 ULD 可包含多個 AWB 的貨件。ULD 復原率不等於 AWB 卸貨率。",
              )}
            </dd>
            <dt>{t("Eligible / all affected", "符合條件 / 全部受影響")}</dt>
            <dd>
              {t(
                "A compliant-path cohort excludes unavoidable no-path cases. Always inspect the separate all-affected denominator.",
                "符合路徑資格的群組不包含無可避免的無路徑個案。必須另外檢視全部受影響單位分母。",
              )}
            </dd>
            <dt>{t("Weighted delay hours", "加權延誤時數")}</dt>
            <dd>
              {t(
                "Delay hours multiplied by a published service weight. This is not money, physical elapsed time or a risk probability.",
                "延誤時數乘以已發布的服務權重。這並非金額、實體經過時間或風險機率。",
              )}
            </dd>
            <dt>OPTIMAL / FEASIBLE / UNKNOWN</dt>
            <dd>
              {t(
                "Optimal is displayed only with confirmed solver status and independent PASS. A time-limited feasible proposal may be reviewed with its termination and gap visible.",
                "僅在求解器確認最優並獨立驗證通過時顯示 Optimal。限時可行方案可在顯示終止原因及差距的情況下審查。",
              )}
            </dd>
            <dt>
              {t(
                "No compliant path / service failure",
                "無合規路徑 / 服務故障",
              )}
            </dt>
            <dd>
              {t(
                "Do not override hard gates. Preserve evidence, stop approval and escalate through your authorised manual procedure. Reconnect to inspect durable job state before requesting another solve.",
                "切勿覆寫硬性條件。保留證據、停止核准，並按照已授權手動程序升級處理。重新連線後，先檢視持久化工作狀態才再次要求求解。",
              )}
            </dd>
          </dl>
        </Section>
      </div>
    </>
  );
}
