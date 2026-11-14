"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Urgency } from "./urgency";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Model, Scenario, Job, Principal } from "@/lib/types";
import { useLocale } from "./locale";
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
export function ScenarioWorkspace({ id }: { id: string }) {
  const { t } = useLocale();
  const router = useRouter();
  const [sourceId, setSourceId] = useState("");
  const resource = useResource<Scenario>(
    `/scenarios/${encodeURIComponent(id)}`,
  );
  const candidates = useResource<Model<"CandidateSet">>(
    `/scenarios/${encodeURIComponent(id)}/candidates`,
  );
  const me = useResource<Principal>("/me");
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [budget, setBudget] = useState(30);
  const [tab, setTab] = useState("overview");
  const [zone, setZone] = useState("UTC");
  const scenario = resource.data;
  const jobId = job?.id || scenario?.latest_job_id;
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const data = await api<Job>(`/jobs/${jobId}`, {
          signal: controller.signal,
        });
        if (cancelled) return;
        setJob(data);
        setError(undefined);
        if (!["COMPLETED", "FAILED", "CANCELLED"].includes(data.status))
          timer = setTimeout(poll, 1800);
        else resource.reload();
      } catch (e) {
        if (!cancelled) {
          setError(e);
          timer = setTimeout(poll, 5000);
        }
      }
    }
    void poll();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [jobId]);
  async function solve() {
    if (!scenario) return;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api<Job>(`/scenarios/${id}/solve`, {
        method: "POST",
        etag: scenario.etag,
        body: {
          max_wall_seconds: budget,
          compare_baselines: true,
        } satisfies Model<"SolveRequest">,
      });
      setJob(result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function supersede(e: React.FormEvent) {
    e.preventDefault();
    if (!scenario) return;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api<Scenario>(`/scenarios/${id}/supersede`, {
        method: "POST",
        etag: scenario.etag,
        body: {
          source_snapshot_id: sourceId,
          title: scenario.snapshot.title,
          allow_external_write: false,
        } satisfies Model<"CreateScenario">,
      });
      router.push(`/operations/${result.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (resource.loading) return <Loading />;
  if (!scenario)
    return (
      <>
        <ErrorNotice error={resource.error} />
        <button className="button" onClick={resource.reload}>
          {t("Retry", "重試")}
        </button>
      </>
    );
  const canSolve =
    me.data?.roles.some((r) => ["controller", "manager"].includes(r)) &&
    scenario.current &&
    ["READY", "PLAN_READY", "SOLVER_ERROR", "NO_FEASIBLE_PLAN"].includes(
      scenario.state,
    ) &&
    !scenario.quality_issues.some((q) => q.blocking) &&
    !job?.status.match(/^(QUEUED|RUNNING|VALIDATING)$/);
  const flightMap = new Map(scenario.snapshot.flights.map((f) => [f.id, f]));
  const pathUnits = new Set(
    candidates.data?.paths.map((p) => p.cargo_unit_id) || [],
  );
  const tabs = [
    ["overview", t("Overview", "總覽")],
    ["candidates", t("Candidate paths", "候選路徑")],
    ["network", t("Routes & cutoffs", "路線及截止時間")],
    ["provenance", t("Source & policy", "來源及政策")],
  ];
  return (
    <>
      <Link className="breadcrumb" href="/operations">
        ← {t("Recovery desk", "復原作業台")}
      </Link>
      <PageHeader
        eyebrow={`RECOVER / ${scenario.snapshot.event_id} / V${scenario.version}`}
        title={scenario.snapshot.title}
        description={t(
          "Review the immutable input before requesting a proposal. All times remain evidence-bound.",
          "要求建議方案前，請檢視不可變更的輸入。所有時間均以證據為依據。",
        )}
        action={<Badge value={scenario.state} />}
      />
      {!scenario.current ? (
        <div className="notice danger">
          {t(
            "Superseded snapshot. Approval and solving require a current scenario.",
            "快照已被取代。核准及求解需要最新情境。",
          )}
        </div>
      ) : null}
      <div className="summary-grid">
        <div>
          <span>{t("Affected cargo", "受影響貨物")}</span>
          <strong>
            {scenario.snapshot.cargo_units.length}
            <small> ULDs</small>
          </strong>
        </div>
        <div>
          <span>{t("Eligible / all affected", "符合條件 / 全部受影響")}</span>
          <strong>
            {candidates.data ? pathUnits.size : "—"}
            <small> / {scenario.snapshot.cargo_units.length} ULDs</small>
          </strong>
        </div>
        <div>
          <span>{t("Input as of", "輸入時間")}</span>
          <strong className="time-value">
            <Time value={scenario.snapshot.as_of} />
          </strong>
        </div>
        <div>
          <span>{t("Valid until", "有效至")}</span>
          <strong className="time-value">
            <Time value={scenario.snapshot.valid_until} />
          </strong>
        </div>
      </div>
      <div className="workspace-grid">
        <div className="workspace-body">
          <div
            className="tabs"
            role="tablist"
            onKeyDown={(e) => {
              const keys = tabs.map(([key]) => key);
              let index = keys.indexOf(tab);
              if (e.key === "ArrowRight") index = (index + 1) % keys.length;
              else if (e.key === "ArrowLeft")
                index = (index - 1 + keys.length) % keys.length;
              else if (e.key === "Home") index = 0;
              else if (e.key === "End") index = keys.length - 1;
              else return;
              e.preventDefault();
              setTab(keys[index]);
              document.getElementById(`tab-${keys[index]}`)?.focus();
            }}
            aria-label={t("Scenario sections", "情境區段")}
          >
            {tabs.map(([key, label]) => (
              <button
                key={key}
                id={`tab-${key}`}
                role="tab"
                tabIndex={tab === key ? 0 : -1}
                aria-selected={tab === key}
                aria-controls={`panel-${key}`}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
            tabIndex={0}
          >
            {tab === "overview" ? (
              <>
                <Section
                  title={t("Affected ULD manifest", "受影響 ULD 貨物清單")}
                >
                  <Table
                    caption={t(
                      "Affected cargo with physical quantities",
                      "附實體數量的受影響貨物",
                    )}
                    headers={[
                      "ULD / AWB",
                      t("Route / service", "路線 / 服務"),
                      t("Mass / volume", "重量 / 體積"),
                      t("Commitment", "承諾時間"),
                      t("Evidence", "證據"),
                    ]}
                  >
                    {scenario.snapshot.cargo_units.map((u) => (
                      <tr key={u.id}>
                        <td>
                          <strong>{u.uld_code}</strong>
                          <small>{u.id}</small>
                          <small>
                            {[...new Set(u.pieces.map((p) => p.awb_id))].join(
                              ", ",
                            )}
                          </small>
                        </td>
                        <td>
                          {u.origin} → {u.destination}
                          <small>
                            {u.service_class} · {t("weight", "權重")}{" "}
                            {u.service_weight}
                          </small>
                        </td>
                        <td>
                          {u.actual_mass_kg} kg
                          <small>{u.actual_volume_m3} m³</small>
                        </td>
                        <td>
                          <Time value={u.commitment_at} />
                          <small>
                            {t("Ready", "備妥")}: <Time value={u.ready_at} />
                          </small>
                        </td>
                        <td>
                          <span>
                            {t("Security", "保安")}: {u.security.state}
                          </span>
                          <small>
                            {t("Serviceability", "可用性")}:{" "}
                            {u.serviceability.state}
                          </small>
                          {candidates.data && !pathUnits.has(u.id) ? (
                            <Badge value="NO_COMPLIANT_PATH" />
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </Table>
                </Section>
                <Section title={t("Quality findings", "資料品質結果")}>
                  {scenario.quality_issues.length ? (
                    <Table
                      caption={t("Input quality issues", "輸入品質問題")}
                      headers={[
                        t("Severity / code", "嚴重程度 / 代碼"),
                        t("Entity / field", "實體 / 欄位"),
                        t("Required remediation", "所需補救措施"),
                      ]}
                    >
                      {scenario.quality_issues.map((q, i) => (
                        <tr key={i}>
                          <td>
                            <Badge
                              value={q.blocking ? "BLOCKING" : q.severity}
                            />
                            <small>{q.code}</small>
                          </td>
                          <td>
                            {q.entity_id}
                            <small>{q.field}</small>
                          </td>
                          <td>{q.remediation}</td>
                        </tr>
                      ))}
                    </Table>
                  ) : (
                    <Empty>
                      {t(
                        "No quality issues reported by the service. This is a synthetic model check, not aviation certification.",
                        "服務未回報品質問題。此為合成模型檢查，並非航空認證。",
                      )}
                    </Empty>
                  )}
                </Section>
              </>
            ) : null}
            {tab === "candidates" ? (
              <>
                <ErrorNotice error={candidates.error} />
                {candidates.loading ? <Loading /> : null}
                <Section title={t("Eligible paths", "符合條件的路徑")}>
                  {candidates.data?.paths.length ? (
                    <Table
                      caption={t(
                        "Verified candidate paths and exact timing",
                        "已驗證候選路徑及精確時間",
                      )}
                      headers={[
                        "ULD / path",
                        t("Flight sequence", "航班序列"),
                        t("Last cutoff / arrival", "最後截止 / 抵達"),
                        t("Delay", "延誤"),
                        t("Why eligible", "符合條件原因"),
                      ]}
                    >
                      {candidates.data.paths.map((p) => (
                        <tr key={p.id}>
                          <td>
                            <strong>{p.cargo_unit_id}</strong>
                            <small>{p.id}</small>
                          </td>
                          <td>
                            {p.legs
                              .map(
                                (l) =>
                                  flightMap.get(l.flight_id)?.flight_number ||
                                  l.flight_id,
                              )
                              .join(" → ")}
                          </td>
                          <td>
                            <Time value={p.cutoff_at} />
                            <small>
                              <Time value={p.arrival_at} />
                            </small>
                          </td>
                          <td>
                            {p.delay_hours} h
                            <small>{p.weighted_delay_hours} weighted h</small>
                          </td>
                          <td>{p.reason_codes.join(" · ")}</td>
                        </tr>
                      ))}
                    </Table>
                  ) : (
                    <Empty>
                      {t(
                        "No compliant paths returned. Review missing evidence and excluded arcs; do not infer eligibility.",
                        "未回傳合規路徑。請檢視缺少的證據及已排除航段，切勿自行推斷資格。",
                      )}
                    </Empty>
                  )}
                </Section>
                <Section
                  title={t(
                    "Excluded arcs / hard gates",
                    "已排除航段 / 硬性條件",
                  )}
                  aside={
                    <span>
                      {candidates.data?.excluded.length ?? "—"}{" "}
                      {t("exclusions", "項排除")}
                    </span>
                  }
                >
                  {candidates.data?.excluded.length ? (
                    <Table
                      caption={t(
                        "Excluded arcs with gate reasons",
                        "附條件原因的已排除航段",
                      )}
                      headers={[
                        "ULD",
                        t("Flight", "航班"),
                        t("Gate", "條件"),
                        t("Reason", "原因"),
                      ]}
                    >
                      {candidates.data.excluded.map((e, i) => (
                        <tr key={i}>
                          <td>{e.cargo_unit_id}</td>
                          <td>{e.flight_id || "—"}</td>
                          <td>
                            <Badge value={`BLOCKED ${e.gate}`} />
                          </td>
                          <td>{e.reason_codes.join(" · ")}</td>
                        </tr>
                      ))}
                    </Table>
                  ) : (
                    <Empty>
                      {t("No exclusions reported.", "未回報排除項目。")}
                    </Empty>
                  )}
                  <JsonDetails
                    value={candidates.data?.quality_issues || []}
                    label={t("Candidate quality findings", "候選路徑品質結果")}
                  />
                  <p className="fine">
                    {t("Pruned paths", "已剪枝路徑")}:{" "}
                    {candidates.data?.pruned_path_count ?? "—"} ·{" "}
                    {candidates.data?.model_scope}
                  </p>
                </Section>
              </>
            ) : null}
            {tab === "network" ? (
              <>
                <Urgency
                  scenarioId={id}
                  cargoUnits={scenario.snapshot.cargo_units}
                  asOf={scenario.snapshot.as_of}
                  validUntil={scenario.snapshot.valid_until}
                />
                <Section
                  title={t("Flight timeline & capacity", "航班時間軸及容量")}
                  aside={
                    <label className="inline-label">
                      {t("Display time zone", "顯示時區")}
                      <select
                        value={zone}
                        onChange={(e) => setZone(e.target.value)}
                      >
                        <option>UTC</option>
                        <option>Asia/Hong_Kong</option>
                        <option>Europe/London</option>
                        <option>Europe/Berlin</option>
                      </select>
                    </label>
                  }
                >
                  <Table
                    caption={t(
                      "Flight routes, exact cutoffs and remaining capacity",
                      "航班路線、精確截止時間及剩餘容量",
                    )}
                    headers={[
                      t("Flight / route", "航班 / 路線"),
                      t("Cutoff", "截止時間"),
                      t("Departure / arrival", "起飛 / 抵達"),
                      t("Capacity", "容量"),
                      t("Verification", "驗證"),
                    ]}
                  >
                    {scenario.snapshot.flights.map((f) => (
                      <tr key={f.id}>
                        <td>
                          <strong>{f.flight_number}</strong>
                          <small>
                            {f.origin} → {f.destination}
                          </small>
                          <small>
                            {f.status} · {f.aircraft_variant}
                          </small>
                        </td>
                        <td>
                          <Time value={f.cutoff_at} zone={zone} />
                        </td>
                        <td>
                          <Time value={f.departure_at} zone={zone} />
                          <small>
                            <Time value={f.arrival_at} zone={zone} />
                          </small>
                        </td>
                        <td>
                          {f.free_mass_kg ?? t("Unknown", "未知")} kg
                          <small>
                            {f.free_volume_m3 ?? t("Unknown", "未知")} m³
                          </small>
                          <small>
                            {f.positions
                              .map(
                                (p) => `${p.id}: ${p.slot_count ?? "?"} slots`,
                              )
                              .join(" · ")}
                          </small>
                        </td>
                        <td>
                          <Badge value={f.capacity_verification.state} />
                          <small>
                            {f.capacity_verification.source_record_id}
                          </small>
                        </td>
                      </tr>
                    ))}
                  </Table>
                  <JsonDetails
                    value={scenario.snapshot.connections}
                    label={t("Explicit connection permissions", "明確轉運許可")}
                  />
                  <JsonDetails
                    value={scenario.snapshot.handling_windows}
                    label={t("Ground handling windows", "地面處理時段")}
                  />
                </Section>
              </>
            ) : null}
            {tab === "provenance" ? (
              <Section title={t("Immutable provenance", "不可變更的來源證據")}>
                <dl className="facts">
                  <dt>{t("Evidence tier", "證據等級")}</dt>
                  <dd>{scenario.snapshot.evidence_tier}</dd>
                  <dt>{t("Source", "來源")}</dt>
                  <dd>{scenario.snapshot.provenance.source_id}</dd>
                  <dt>{t("Observed", "觀測時間")}</dt>
                  <dd>
                    <Time value={scenario.snapshot.provenance.observed_at} />
                  </dd>
                  <dt>{t("Ingested", "匯入時間")}</dt>
                  <dd>
                    <Time value={scenario.snapshot.provenance.ingested_at} />
                  </dd>
                  <dt>{t("Snapshot hash", "快照雜湊值")}</dt>
                  <dd>
                    <Hash value={scenario.snapshot_hash} />
                  </dd>
                  <dt>{t("Policy hash", "政策雜湊值")}</dt>
                  <dd>
                    <Hash value={scenario.policy_hash} />
                  </dd>
                </dl>
                <JsonDetails
                  value={scenario.snapshot.policy}
                  label={t("Published policy details", "已發布政策詳情")}
                />
                <JsonDetails
                  value={scenario.snapshot}
                  label={t("Full immutable input", "完整不可變更輸入")}
                />
              </Section>
            ) : null}
          </div>
        </div>
        <aside className="decision-rail">
          <p className="eyebrow">{t("PROPOSAL CONTROL", "建議方案控制")}</p>
          <h2>{t("Request a verified plan", "要求已驗證方案")}</h2>
          <p>
            {t(
              "The worker compares network allocation with earliest-feasible and priority-first reference heuristics on the same snapshot.",
              "工作程序會以同一快照，比較網絡分配與最早可行及優先順序參考啟發法。",
            )}
          </p>
          <label>
            {t("Solve budget (seconds)", "求解時間上限（秒）")}
            <select
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            >
              {[10, 30, 60].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <button
            className="button primary wide"
            onClick={solve}
            disabled={!canSolve || busy}
          >
            {busy
              ? t("Submitting…", "正在提交……")
              : t("Solve & compare", "求解並比較")}
          </button>
          {!canSolve ? (
            <p className="fine">
              {t(
                "Requires a current, ready snapshot, no blocking quality issues and a Controller or Manager role.",
                "需要最新、已備妥的快照、沒有阻擋性品質問題，以及 Controller 或 Manager 角色。",
              )}
            </p>
          ) : null}
          <ErrorNotice error={error} />
          {job ? (
            <div className="job" aria-live="polite">
              <h3>{t("Durable solve job", "持久化求解工作")}</h3>
              <Badge value={job.status} />
              <p>
                {t("Attempt", "嘗試次數")} {job.attempt} · {job.progress}%
              </p>
              <progress
                max={100}
                value={job.progress}
                aria-label={t("Solve progress", "求解進度")}
              />
              <code>{job.id}</code>
              <p>
                <Time value={job.started_at || job.created_at} />
              </p>
              {job.error_code ? (
                <div className="notice danger">
                  <strong>{job.error_code}</strong>
                  <p>
                    {t(
                      "No successful result is implied. Retry after resolving the cause or escalate through your operating procedure.",
                      "不代表已有成功結果。解決原因後重試，或按照作業程序升級處理。",
                    )}
                  </p>
                </div>
              ) : null}
              {job.plan_id ? (
                <Link className="button wide" href={`/plans/${job.plan_id}`}>
                  {t("Review proposal", "檢視建議方案")} →
                </Link>
              ) : null}
              <p className="fine">
                {t(
                  "The job remains on the server when you leave this page. Polling resumes from its recorded ID.",
                  "離開此頁後，工作仍保留於伺服器。系統會以記錄的 ID 恢復輪詢。",
                )}
              </p>
            </div>
          ) : null}
          {scenario.latest_plan_id && !job?.plan_id ? (
            <Link
              className="button wide"
              href={`/plans/${scenario.latest_plan_id}`}
            >
              {t("Open latest plan", "開啟最新方案")}
            </Link>
          ) : null}
          <details className="raw">
            <summary>
              {t(
                "Supersede with a newer committed source",
                "以較新的已提交來源取代",
              )}
            </summary>
            <p>
              {t(
                "Creates a new immutable version. Existing plans and decisions remain in the audit trail.",
                "建立新的不可變更版本。現有方案及決策仍會保留於稽核紀錄。",
              )}
            </p>
            <form onSubmit={supersede}>
              <label>
                {t("New committed source ID", "新的已提交來源 ID")}
                <input
                  required
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                  pattern="[a-fA-F0-9-]{36}"
                  placeholder="UUID"
                />
              </label>
              <button
                className="button"
                disabled={
                  busy ||
                  !sourceId ||
                  !me.data?.roles.some((r) =>
                    ["controller", "manager"].includes(r),
                  )
                }
              >
                {t("Create superseding version", "建立取代版本")}
              </button>
            </form>
          </details>
          <div className="rail-boundary">
            {t("IN-APP DECISION ONLY", "僅限應用程式內決策")}
            <p>
              {t(
                "No dispatch. No airline write-back. Unknown hard gates cannot be overridden.",
                "不會執行調度或航空公司寫入。未知的硬性條件不能被覆寫。",
              )}
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
