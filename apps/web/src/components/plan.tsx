"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Model, Plan, Principal, Scenario } from "@/lib/types";
import { useLocale } from "./locale";
import { FlightTimeline, PolicyComparison } from "./charts";
import { Metrics } from "./metrics";
import { ReportExport } from "./report-export";
import {
  Badge,
  Empty,
  ErrorNotice,
  Hash,
  JsonDetails,
  Loading,
  PageHeader,
  Section,
  Table,
  Time,
  useResource,
} from "./ui";
export function PlanReview({ id }: { id: string }) {
  const { t } = useLocale();
  const resource = useResource<Plan>(`/plans/${encodeURIComponent(id)}`);
  const alternatives = useResource<Model<"PlanList">>(
    `/plans/${encodeURIComponent(id)}/alternatives`,
  );
  const scenario = useResource<Scenario>(
    resource.data ? `/scenarios/${resource.data.scenario_id}` : null,
  );
  const me = useResource<Principal>("/me");
  const [action, setAction] =
    useState<Model<"DecisionRequest">["action"]>("APPROVE_IN_APP");
  const [reason, setReason] = useState("REVIEWED_VALIDATED_PLAN");
  const [comment, setComment] = useState("");
  const [confirm, setConfirm] = useState("");
  const [hashConfirmed, setHashConfirmed] = useState(false);
  const [receipt, setReceipt] = useState<Model<"DecisionReceipt">>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const record = resource.data;
  if (resource.loading) return <Loading />;
  if (!record)
    return (
      <>
        <ErrorNotice error={resource.error} />
        <button className="button" onClick={resource.reload}>
          {t("Retry", "重試")}
        </button>
      </>
    );
  const plan = record.plan;
  const pass = plan.independent_validation.status === "PASS";
  const canDecide = me.data?.roles.some((r) =>
    ["controller", "manager"].includes(r),
  );
  const approvable =
    record.approvable &&
    pass &&
    record.state === "PROPOSED" &&
    scenario.data?.current;
  const optimal = plan.solver.status === "OPTIMAL" && pass;
  const flights = new Map(
    scenario.data?.snapshot.flights.map((f) => [f.id, f]) || [],
  );
  async function decide(e: React.FormEvent) {
    e.preventDefault();
    if (!record) return;
    setError(undefined);
    setBusy(true);
    try {
      const result = await api<Model<"DecisionReceipt">>(
        `/plans/${id}/decisions`,
        {
          method: "POST",
          etag: record.etag,
          body: {
            action,
            reason_code: reason,
            comment,
            expected_snapshot_hash: record.plan.snapshot_hash,
            expected_plan_hash: record.plan_hash,
          } satisfies Model<"DecisionRequest">,
        },
      );
      setReceipt(result);
      resource.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="breadcrumb" href={`/operations/${record.scenario_id}`}>
        ← {t("Scenario workspace", "情境工作區")}
      </Link>
      <PageHeader
        eyebrow={`DECISION REVIEW / V${record.scenario_version}`}
        title={t("Recovery proposal", "復原建議方案")}
        description={t(
          "Compare assignments and reference heuristics. Record a decision only after verifying the exact proposal.",
          "比較分配方案及參考啟發法。核對完整建議方案後才記錄決策。",
        )}
        action={
          <div className="header-actions">
            <Link className="button primary" href={`/plans/${id}/console`}>
              {t("Open dispatcher console", "開啟調度控制台")}
            </Link>
            <Badge value={record.state} />
          </div>
        }
      />
      <div className={`notice ${pass ? "success" : "danger"}`}>
        <strong>
          {pass
            ? t("Independent validation PASS", "獨立驗證通過")
            : t("QUARANTINED — validation failed", "隔離處理 — 驗證失敗")}
        </strong>
        <p>
          {t(
            "Synthetic conservative envelope only. This does not certify aircraft balance, physical packing or dangerous-goods compliance.",
            "僅適用於合成保守包絡模型。並不認證飛機平衡、實體裝載或危險品合規。",
          )}
        </p>
        <span>
          {t("Checked gates", "已檢查條件")}:{" "}
          {plan.independent_validation.checked_gates.join(" · ")}
        </span>
      </div>
      {record.blockers.length ? (
        <div className="notice danger">
          <strong>{t("Decision blockers", "決策阻擋項目")}</strong>
          <ul>
            {record.blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="summary-grid">
        <div>
          <span>{t("Solver outcome", "求解結果")}</span>
          <strong className="status-value">
            {optimal
              ? "OPTIMAL"
              : plan.solver.status === "OPTIMAL"
                ? "NEEDS VERIFICATION"
                : plan.solver.status.replaceAll("_", " ")}
          </strong>
          <small>
            {plan.solver.engine} {plan.solver.version}
          </small>
        </div>
        <div>
          <span>{t("Proposed / unassigned", "建議分配 / 未分配")}</span>
          <strong>
            {plan.assignments.length}
            <small> / {plan.unassigned.length} ULDs</small>
          </strong>
        </div>
        <div>
          <span>{t("Measured solve time", "實測求解時間")}</span>
          <strong>
            {(Number(plan.solver.wall_time_ms) / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            <small> s</small>
          </strong>
          <small>
            {t("Budget", "上限")}: {plan.solver.time_limit_seconds} s
          </small>
        </div>
        <div>
          <span>{t("Optimality gap", "最優性差距")}</span>
          <strong>
            {plan.solver.optimality_gap === null
              ? "—"
              : `${(Number(plan.solver.optimality_gap) * 100).toLocaleString(undefined, { maximumFractionDigits: 3 })}%`}
          </strong>
          <small>
            {t("Bound", "界限")}: {plan.solver.best_bound ?? "—"}
          </small>
        </div>
      </div>
      <Section title={t("CargoPulse vs simple rules on the same snapshot", "相同快照下 CargoPulse 對比簡單規則")}>
        {alternatives.loading ? (
          <Loading />
        ) : (
          <PolicyComparison plan={record} alternatives={alternatives.data?.items || []} />
        )}
      </Section>
      {scenario.data ? (
        <Section title={t("Flight timeline", "航班時間軸")}>
          <FlightTimeline snapshot={scenario.data.snapshot} assignments={plan.assignments} />
        </Section>
      ) : null}
      <div className="workspace-grid">
        <div className="workspace-body">
          <Section
            title={t("Proposed assignments", "建議分配")}
            aside={<ReportExport id={id} />}
          >
            <Table
              caption={t("Whole-ULD proposed assignments", "整體 ULD 建議分配")}
              headers={[
                "ULD / path",
                t("Flight / position / handling", "航班 / 貨位 / 處理時段"),
                t("Arrival", "抵達時間"),
                t("Delay", "延誤"),
                t("Change / reasons", "變更 / 原因"),
              ]}
            >
              {plan.assignments.map((a) => (
                <tr key={a.cargo_unit_id}>
                  <td>
                    <strong>{a.cargo_unit_id}</strong>
                    <small>{a.path_id}</small>
                  </td>
                  <td>
                    {a.legs.map((l, i) => (
                      <div key={i}>
                        {flights.get(l.flight_id)?.flight_number || l.flight_id}
                        <small>
                          {l.position_id} · {l.handling_window_id}
                        </small>
                      </div>
                    ))}
                  </td>
                  <td>
                    <Time value={a.arrival_at} />
                  </td>
                  <td>
                    {a.delay_hours} h
                    <small>{a.weighted_delay_hours} weighted h</small>
                  </td>
                  <td>
                    <Badge
                      value={a.changed_from_previous ? "CHANGED" : "UNCHANGED"}
                    />
                    <small>{a.reason_codes.join(" · ")}</small>
                  </td>
                </tr>
              ))}
            </Table>
            {!plan.assignments.length ? (
              <Empty>
                {t(
                  "No ULD is assigned. Do not treat this as a successful recovery.",
                  "沒有 ULD 獲分配。不可視為成功復原。",
                )}
              </Empty>
            ) : null}
          </Section>
          <Section
            title={t(
              "Unassigned / escalation required",
              "未分配 / 需要升級處理",
            )}
          >
            {plan.unassigned.length ? (
              <Table
                caption={t(
                  "Unassigned ULDs with escalation reasons",
                  "附升級原因的未分配 ULD",
                )}
                headers={["ULD", t("Reasons", "原因"), t("Action", "處理措施")]}
              >
                {plan.unassigned.map((u) => (
                  <tr key={u.cargo_unit_id}>
                    <td>{u.cargo_unit_id}</td>
                    <td>{u.reason_codes.join(" · ")}</td>
                    <td>
                      <Badge value={u.action} />
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty>
                {t(
                  "No unassigned ULDs in this proposal.",
                  "此建議方案沒有未分配 ULD。",
                )}
              </Empty>
            )}
          </Section>
          <Section
            title={t(
              "Same-snapshot reference comparisons",
              "同一快照的參考比較",
            )}
          >
            <p>
              {t(
                "Earliest-feasible and priority-first are reference heuristics, not an airline’s operating policy. Compare the same metric, denominator and hash.",
                "最早可行及優先順序為參考啟發法，並非航空公司的作業政策。請比較相同指標、分母及雜湊值。",
              )}
            </p>
            <ErrorNotice error={alternatives.error} />
            {alternatives.loading ? <Loading /> : null}
            {alternatives.data?.items.length ? (
              <Table
                caption={t("Alternative validated plans", "其他已驗證方案")}
                headers={[
                  t("Reference / state", "參考 / 狀態"),
                  t("Validation / solver", "驗證 / 求解器"),
                  t("Assignments / unassigned", "已分配 / 未分配"),
                  t("Measured time", "實測時間"),
                  t("Review", "檢視"),
                ]}
              >
                {alternatives.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.plan.solver.engine}
                      <small>{p.state}</small>
                    </td>
                    <td>
                      <Badge value={p.plan.independent_validation.status} />
                      <small>{p.plan.solver.status}</small>
                    </td>
                    <td>
                      {p.plan.assignments.length} / {p.plan.unassigned.length}{" "}
                      ULDs
                    </td>
                    <td>{p.plan.solver.wall_time_ms} ms</td>
                    <td>
                      <Link href={`/plans/${p.id}`}>
                        {t("Open comparison", "開啟比較")} →
                      </Link>
                      <JsonDetails
                        value={p.plan.metrics}
                        label={t("Metric comparison", "指標比較")}
                      />
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty>
                {t("No comparison plans returned.", "未回傳比較方案。")}
              </Empty>
            )}
          </Section>
          <Section
            title={t("Proposal metrics & denominator", "建議方案指標及分母")}
          >
            <Metrics items={plan.metrics} />
          </Section>
          <Section title={t("Solver & validation evidence", "求解及驗證證據")}>
            <p>{plan.solver.termination_reason}</p>
            <JsonDetails
              value={plan.solver}
              label={t("Solver telemetry", "求解器遙測")}
            />
            <JsonDetails
              value={plan.independent_validation}
              label={t("Independent validation report", "獨立驗證報告")}
            />
            <JsonDetails
              value={plan}
              label={t("Complete proposal record", "完整建議方案紀錄")}
            />
          </Section>
        </div>
        <aside className="decision-rail" id="human-decision">
          <p className="eyebrow">{t("HUMAN DECISION", "人員決策")}</p>
          <h2>{t("Review & record", "檢視並記錄")}</h2>
          <p>
            {t(
              "Your decision remains inside CargoPulse. It does not dispatch cargo or update an airline system.",
              "決策僅保留於 CargoPulse，不會調度貨物或更新航空公司系統。",
            )}
          </p>
          <dl className="facts stacked">
            <dt>{t("Plan ID", "方案 ID")}</dt>
            <dd>
              <code>{record.id}</code>
            </dd>
            <dt>{t("Snapshot SHA-256", "快照 SHA-256")}</dt>
            <dd>
              <Hash value={plan.snapshot_hash} />
            </dd>
            <dt>{t("Plan SHA-256", "方案 SHA-256")}</dt>
            <dd>
              <Hash value={record.plan_hash} />
            </dd>
            <dt>{t("Policy SHA-256", "政策 SHA-256")}</dt>
            <dd>
              <Hash value={plan.policy_hash} />
            </dd>
          </dl>
          {receipt ? (
            <div role="status" className="notice success">
              <h3>{t("Immutable decision receipt", "不可變更的決策收據")}</h3>
              <Badge value={receipt.action} />
              <p>{receipt.actor}</p>
              <p>
                <Time value={receipt.recorded_at} />
              </p>
              <code>{receipt.id}</code>
              <p>{t("External write performed: NO", "已執行外部寫入：否")}</p>
              <JsonDetails
                value={receipt}
                label={t("Full receipt", "完整收據")}
              />
            </div>
          ) : (
            <form onSubmit={decide}>
              <label>
                {t("Decision", "決策")}
                <select
                  value={action}
                  onChange={(e) => {
                    setAction(
                      e.target.value as Model<"DecisionRequest">["action"],
                    );
                    setConfirm("");
                  }}
                >
                  <option value="APPROVE_IN_APP" disabled={!approvable}>
                    {t("Approve in-app", "在應用程式內核准")}
                  </option>
                  <option value="REJECT">{t("Reject", "拒絕")}</option>
                  <option value="ESCALATE">{t("Escalate", "升級處理")}</option>
                </select>
              </label>
              <label>
                {t("Reason code", "原因代碼")}
                <input
                  required
                  value={reason}
                  maxLength={100}
                  pattern="[A-Za-z0-9_.:-]+"
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <label>
                {t("Decision rationale", "決策理由")}
                <textarea
                  required
                  minLength={1}
                  maxLength={500}
                  rows={4}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder={t(
                    "Explain the reviewed evidence. Avoid personal or confidential descriptions.",
                    "說明已檢視的證據。避免個人或機密描述。",
                  )}
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={hashConfirmed}
                  onChange={(e) => setHashConfirmed(e.target.checked)}
                />
                <span>
                  {t(
                    "I verified the full snapshot and plan hashes shown above.",
                    "我已核對上方完整的快照及方案雜湊值。",
                  )}
                </span>
              </label>
              <label>
                {t(
                  "Type the exact action to confirm",
                  "輸入完整動作名稱以確認",
                )}
                <code>{action}</code>
                <input
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
              <button
                className="button primary wide"
                disabled={
                  busy ||
                  !canDecide ||
                  !hashConfirmed ||
                  confirm !== action ||
                  !comment.trim() ||
                  (action === "APPROVE_IN_APP" && !approvable) ||
                  record.state !== "PROPOSED"
                }
              >
                {busy
                  ? t("Recording…", "正在記錄……")
                  : t("Record decision", "記錄決策")}
              </button>
              {!canDecide ? (
                <p className="fine">
                  {t(
                    "Controller or Manager role required.",
                    "需要 Controller 或 Manager 角色。",
                  )}
                </p>
              ) : null}
              {!approvable ? (
                <p className="danger-text">
                  {t(
                    "Approval is blocked. Review the server blockers, current snapshot and independent validation.",
                    "核准已被阻擋。請檢視伺服器阻擋項目、最新快照及獨立驗證。",
                  )}
                </p>
              ) : null}
            </form>
          )}
          <ErrorNotice error={error} />
          <button
            className="quiet"
            onClick={() => {
              resource.reload();
              scenario.reload();
            }}
          >
            {t("Refresh current record", "重新整理最新紀錄")}
          </button>
          <Link className="text-link" href="/audit">
            {t("Inspect audit trail", "檢視稽核紀錄")} →
          </Link>
        </aside>
      </div>
    </>
  );
}
