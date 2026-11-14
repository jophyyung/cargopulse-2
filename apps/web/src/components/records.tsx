"use client";
import { useState } from "react";
import { PolicyWorkflow } from "./policy-workflow";
import type { Model } from "@/lib/types";
import { useLocale } from "./locale";
import { downloadJson, Metrics } from "./metrics";
import {
  Badge,
  Empty,
  ErrorNotice,
  Hash,
  Loading,
  PageHeader,
  Section,
  Table,
  Time,
  useResource,
} from "./ui";
export function Evidence() {
  const { t } = useLocale();
  const result = useResource<Model<"MetricsPage">>("/metrics");
  return (
    <>
      <PageHeader
        eyebrow={t("EVIDENCE / PROVENANCE", "證據 / 來源")}
        title={t(
          "Measured proposals. Explicit limits.",
          "可量測的建議。明確的限制。",
        )}
        description={t(
          "Metrics from stored plans only. Synthetic proposals do not establish physical recovery or operating performance.",
          "僅採用儲存方案中的指標。合成建議並不能證明實體復原或作業表現。",
        )}
        action={
          <button
            className="button"
            disabled={!result.data?.items.length}
            onClick={() =>
              downloadJson(result.data, "cargopulse-metrics-synthetic.json")
            }
          >
            {t("Export displayed evidence", "匯出已顯示證據")}
          </button>
        }
      />
      <div className="notice">
        <strong>SYNTHETIC / NOT CONNECTED</strong>
        <p>
          {t(
            "No replay distribution or p50/p95/p99 is published here without a measured cohort. Each row retains its method, denominator, baseline and exact input hashes.",
            "沒有實測群組時，不會發布重播分布或 p50/p95/p99。每筆紀錄均保留其方法、分母、基準及完整輸入雜湊值。",
          )}
        </p>
      </div>
      <ErrorNotice error={result.error} />
      {result.loading ? <Loading /> : null}
      <Section
        title={t("Stored plan metrics", "已儲存方案指標")}
        aside={
          <button className="quiet" onClick={result.reload}>
            {t("Refresh", "重新整理")}
          </button>
        }
      >
        <Metrics items={result.data?.items || []} />
      </Section>
    </>
  );
}
export function Policies() {
  const { t } = useLocale();
  const result = useResource<Model<"PolicyPage">>("/policies");
  return (
    <>
      <PageHeader
        eyebrow={t("GOVERNANCE / PUBLISHED RULES", "治理 / 已發布規則")}
        title={t("Policy register", "政策登記冊")}
        description={t(
          "Published, immutable rules referenced by snapshot and policy hash. Synthetic reviewers do not constitute airline sign-off.",
          "已發布的不可變更規則，以快照及政策雜湊值引用。合成審查者並不代表航空公司簽核。",
        )}
      />
      <ErrorNotice error={result.error} />
      {result.loading ? <Loading /> : null}
      <Section title={t("Published versions", "已發布版本")}>
        {result.data?.items.length ? (
          <Table
            caption={t("Published recovery policies", "已發布的復原政策")}
            headers={[
              t("Policy / version", "政策 / 版本"),
              t("Author / reviewer", "作者 / 審核者"),
              t("Timing rules", "時間規則"),
              t("Objective penalties", "目標懲罰值"),
              t("Scope / published", "範圍 / 發布時間"),
            ]}
          >
            {result.data.items.map((p) => (
              <tr key={`${p.id}-${p.version}`}>
                <td>
                  <strong>{p.id}</strong>
                  <small>{p.version}</small>
                  <Badge value={p.state} />
                </td>
                <td>
                  {p.authored_by}
                  <small>→ {p.approved_by}</small>
                </td>
                <td>
                  {p.handling_seconds} s {t("handling", "處理")}
                  <small>
                    {p.source_max_age_seconds} s{" "}
                    {t("source max age", "來源最長時效")}
                  </small>
                  <small>
                    {p.max_legs} {t("maximum legs", "最多航段")}
                  </small>
                </td>
                <td>
                  {t("Unassigned", "未分配")}:{" "}
                  {p.unassigned_penalty_weighted_hours} weighted h
                  <small>
                    {t("Handling", "處理")}: {p.handling_penalty_weighted_hours}{" "}
                    weighted h
                  </small>
                  <small>
                    {t("Stability", "穩定性")}:{" "}
                    {p.stability_penalty_weighted_hours} weighted h
                  </small>
                </td>
                <td>
                  {p.model_scope}
                  <small>
                    <Time value={p.published_at} />
                  </small>
                </td>
              </tr>
            ))}
          </Table>
        ) : !result.loading ? (
          <Empty>
            {t("No published policies available.", "沒有可用的已發布政策。")}
          </Empty>
        ) : null}
      </Section>
      <PolicyWorkflow
        policies={result.data?.items || []}
        onPublished={result.reload}
      />
    </>
  );
}
export function Audit() {
  const { t } = useLocale();
  const [cursor, setCursor] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const result = useResource<Model<"AuditPage">>(
    `/audit?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
  );
  const items = result.data?.items.filter((a) =>
    `${a.action} ${a.resource_id} ${a.actor} ${a.outcome}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow={t("GOVERNANCE / ACCOUNTABILITY", "治理 / 問責")}
        title={t("Audit trail", "稽核紀錄")}
        description={t(
          "Tenant-scoped, permissioned audit records. Corrections append new events; historical decisions remain immutable.",
          "按租戶及權限範圍顯示稽核紀錄。更正會新增事件；歷史決策保持不可變更。",
        )}
        action={
          <button
            className="button"
            disabled={!result.data?.items.length}
            onClick={() =>
              downloadJson(result.data, "cargopulse-audit-page.json")
            }
          >
            {t("Export this page · JSON", "匯出此頁 · JSON")}
          </button>
        }
      />
      <div className="toolbar">
        <label>
          {t("Filter loaded page", "篩選已載入頁面")}
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t(
              "Actor, action, outcome or resource",
              "執行者、動作、結果或資源",
            )}
          />
        </label>
        <button className="button" onClick={result.reload}>
          {t("Refresh", "重新整理")}
        </button>
      </div>
      <ErrorNotice error={result.error} />
      {result.loading ? <Loading /> : null}
      <Section title={t("Recorded events", "已記錄事件")}>
        {items?.length ? (
          <Table
            caption={t("Tenant audit records", "租戶稽核紀錄")}
            headers={[
              t("Time / actor", "時間 / 執行者"),
              t("Action / outcome", "動作 / 結果"),
              t("Resource", "資源"),
              t("Integrity / reference", "完整性 / 參考"),
            ]}
          >
            {items.map((a) => (
              <tr key={a.id}>
                <td>
                  <Time value={a.occurred_at} />
                  <small>{a.actor}</small>
                </td>
                <td>
                  <strong>{a.action}</strong>
                  <small>
                    <Badge value={a.outcome} />
                  </small>
                </td>
                <td>
                  <code>{a.resource_id}</code>
                </td>
                <td>
                  <details>
                    <summary>
                      {t("Hashes & correlation", "雜湊值及關聯編號")}
                    </summary>
                    <Hash value={a.event_hash} />
                    <Hash value={a.previous_hash} />
                    <code>{a.correlation_id}</code>
                  </details>
                </td>
              </tr>
            ))}
          </Table>
        ) : !result.loading && !result.error ? (
          <Empty>
            {t(
              "No audit events match this page. Auditor or Manager access is required.",
              "此頁沒有符合條件的稽核事件。需要 Auditor 或 Manager 存取權限。",
            )}
          </Empty>
        ) : null}
        <div className="actions">
          <button
            className="button"
            disabled={!cursor}
            onClick={() => setCursor(null)}
          >
            {t("First page", "第一頁")}
          </button>
          <button
            className="button"
            disabled={!result.data?.next_cursor}
            onClick={() => setCursor(result.data?.next_cursor || null)}
          >
            {t("Next page", "下一頁")} →
          </button>
        </div>
      </Section>
    </>
  );
}
