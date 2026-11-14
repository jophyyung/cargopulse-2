"use client";
import Link from "next/link";
import { useState } from "react";
import type { Model, Plan, Scenario } from "@/lib/types";
import { FlightTimeline, PolicyComparison, policyLabel } from "./charts";
import { useLocale } from "./locale";
import { ErrorNotice, Loading, Time, useResource } from "./ui";

type Row = {
  id: string;
  unit: Model<"CargoUnit">;
  assignment?: Model<"Assignment">;
  unassigned?: Model<"Unassigned">;
  flight?: Model<"FlightCapacity">;
  rvar: number | null | undefined; // undefined = not computed, null = all paths lost
  status: "ESCALATE" | "FREIGHTER_ONLY" | "ACT_NOW" | "MUST_MAKE" | "CAN_WAIT";
};

const fmt = (n: number, digits = 1) =>
  n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export function DispatchConsole({ id }: { id: string }) {
  const { t } = useLocale();
  const plan = useResource<Plan>(`/plans/${encodeURIComponent(id)}`);
  const alternatives = useResource<Model<"PlanList">>(`/plans/${encodeURIComponent(id)}/alternatives`);
  const sid = plan.data?.scenario_id;
  const scenario = useResource<Scenario>(sid ? `/scenarios/${sid}` : null);
  // What-if urgency: evidence held at snapshot time, so R-VaR reflects real cutoff cliffs.
  const urgency = useResource<Model<"UrgencyPoint">[]>(sid ? `/scenarios/${sid}/urgency?evidence=hold` : null);
  const candidates = useResource<Model<"CandidateSet">>(sid ? `/scenarios/${sid}/candidates` : null);
  const [selected, setSelected] = useState<string>();
  const [all, setAll] = useState(false);

  if (plan.loading || (sid && scenario.loading)) return <Loading />;
  if (!plan.data || !scenario.data)
    return <ErrorNotice error={plan.error || scenario.error} />;
  const record = plan.data;
  const snap = scenario.data.snapshot;
  const asOf = Date.parse(snap.as_of);
  const flights = new Map(snap.flights.map((f) => [f.id, f]));
  const units = new Map(snap.cargo_units.map((u) => [u.id, u]));
  const points = urgency.data || [];
  const pointsByUnit = new Map<string, Model<"UrgencyPoint">[]>();
  for (const p of points) pointsByUnit.set(p.cargo_unit_id, [...(pointsByUnit.get(p.cargo_unit_id) || []), p]);
  for (const list of pointsByUnit.values()) list.sort((a, b) => Date.parse(a.decision_at) - Date.parse(b.decision_at));
  const h = (iso: string) => (Date.parse(iso) - asOf) / 3_600_000;

  // R-VaR: extra weighted delay if the decision waits past this ULD's assigned cutoff.
  const rvarAfter = (unitId: string, cutoff: string) => {
    if (!urgency.data) return undefined;
    const after = (pointsByUnit.get(unitId) || []).find((p) => Date.parse(p.decision_at) > Date.parse(cutoff));
    if (!after) return 0;
    return after.delta_weighted_hours === null ? null : Number(after.delta_weighted_hours);
  };
  const rows: Row[] = [
    ...record.plan.assignments.map((a) => {
      const unit = units.get(a.cargo_unit_id)!;
      const flight = flights.get(a.legs[0]?.flight_id ?? "");
      const rvar = flight ? rvarAfter(a.cargo_unit_id, flight.cutoff_at) : undefined;
      const risky = rvar === null || (rvar ?? 0) > 0;
      const soon = flight ? h(flight.cutoff_at) <= 6 : false;
      const status: Row["status"] =
        unit?.dg_class === "FREIGHTER_ONLY" ? "FREIGHTER_ONLY" : risky ? (soon ? "ACT_NOW" : "MUST_MAKE") : "CAN_WAIT";
      return { id: a.cargo_unit_id, unit, assignment: a, flight, rvar, status };
    }),
    ...record.plan.unassigned.map((u) => ({
      id: u.cargo_unit_id,
      unit: units.get(u.cargo_unit_id)!,
      unassigned: u,
      rvar: undefined,
      status: "ESCALATE" as const,
    })),
  ].filter((r) => r.unit);
  const rank = (r: Row) => (r.rvar === null ? 1e9 : r.status === "ESCALATE" ? 5e8 : (r.rvar ?? -1));
  const cut = (r: Row) => (r.flight ? Date.parse(r.flight.cutoff_at) : Infinity);
  rows.sort((a, b) => rank(b) - rank(a) || cut(a) - cut(b) || a.id.localeCompare(b.id));
  const changed = record.plan.assignments.filter((a) => a.changed_from_previous).length;
  const visible = all ? rows : rows.slice(0, 12);
  const current = rows.find((r) => r.id === selected) || rows[0];

  // Recovery regret: total extra weighted delay if nothing is decided before the next cutoff.
  const nextTime = [...new Set(points.map((p) => p.decision_at))]
    .filter((iso) => Date.parse(iso) > asOf)
    .toSorted((a, b) => Date.parse(a) - Date.parse(b))[0];
  const atNext = points.filter((p) => p.decision_at === nextTime);
  const regret = atNext.reduce((s, p) => s + Number(p.delta_weighted_hours ?? 0), 0);
  const lostAtNext = atNext.filter((p) => p.delta_weighted_hours === null).length;
  const hub = snap.flights.map((f) => f.origin).toSorted((a, b) =>
    snap.flights.filter((f) => f.origin === b).length - snap.flights.filter((f) => f.origin === a).length,
  )[0];
  const cancelled = snap.flights.filter((f) => f.status === "CANCELLED");
  const solver = record.plan.solver;
  const statusLabel: Record<Row["status"], string> = {
    ACT_NOW: t("Act now", "立即恢復"),
    MUST_MAKE: t("Must make cutoff", "須趕上截載"),
    CAN_WAIT: t("Can wait", "可等待"),
    ESCALATE: t("Escalate", "上報"),
    FREIGHTER_ONLY: t("Freighter only", "只限貨機"),
  };

  return (
    <div className="console">
      <Link className="breadcrumb" href={`/plans/${id}`}>
        ← {t("Decision sheet & evidence", "決策表及證據")}
      </Link>
      <header className="console-bar">
        <div>
          <strong>CargoPulse</strong>
          <span>
            {t("Recovery console", "恢復控制台")} · {hub} · {snap.title}
          </span>
        </div>
        <div className="console-bar-meta">
          <span>
            {t("Data as of", "數據更新")} <Time value={snap.as_of} />
          </span>
          <span className={`console-chip ${record.plan.independent_validation.status === "PASS" ? "ok" : "bad"}`}>
            {solver.status.replaceAll("_", " ")} · {fmt(Number(solver.wall_time_ms) / 1000, 2)} s ·{" "}
            {record.plan.independent_validation.status === "PASS"
              ? t("validated", "已驗證")
              : t("validation failed", "驗證失敗")}
          </span>
        </div>
      </header>
      <div className="console-grid">
        <aside className="console-col" aria-label={t("Events", "事件")}>
          <h2>{t("Events", "即時事件")}</h2>
          <div className="event-card warn">
            <strong>{t("Disruption", "中斷事件")}</strong>
            <span>{snap.title}</span>
            <small>
              {rows.length} {t("ULDs affected", "個受影響 ULD")} · <Time value={snap.as_of} />
            </small>
          </div>
          {cancelled.slice(0, 4).map((f) => (
            <div key={f.id} className="event-card danger">
              <strong>{t("Flight cancelled", "航班取消")}</strong>
              <span>
                {f.flight_number} {f.origin}→{f.destination}
              </span>
              <small>
                {t("was due", "原定")} +{fmt(h(f.departure_at))}h
              </small>
            </div>
          ))}
          {scenario.data.quality_issues.length ? (
            <div className="event-card warn">
              <strong>{t("Data quality", "數據品質")}</strong>
              <span>
                {scenario.data.quality_issues.length} {t("issues need review", "項問題待檢視")}
              </span>
            </div>
          ) : null}
          <div className="event-card ok">
            <strong>{t("Escalations", "上報")}</strong>
            <span>
              {record.plan.unassigned.length} {t("ULDs without a compliant flight", "個 ULD 沒有合規航班")}
            </span>
          </div>
          <div className="regret">
            <span>{t("Recovery regret", "恢復遺憾值")}</span>
            {urgency.data && nextTime ? (
              <>
                <strong>+{fmt(regret)}</strong>
                <small>
                  {t("extra weighted hours if nothing is decided before the next cutoff", "若在下一個截載前不行動的額外加權小時")} (+
                  {fmt(h(nextTime))}h)
                  {lostAtNext ? ` · ${lostAtNext} ${t("ULDs would lose every path", "個 ULD 會失去所有路徑")}` : ""}
                </small>
              </>
            ) : (
              <small>{t("Requires controller or manager access.", "需要調度員或經理權限。")}</small>
            )}
          </div>
        </aside>

        <section className="console-col console-main" aria-label={t("Proposed plan", "建議方案")}>
          <h2>
            {t("Proposed plan", "建議方案")} · {rows.length} {t("affected ULDs", "個受影響 ULD")} · {changed}{" "}
            {t("changes vs current", "項較現行變更")}
          </h2>
          <div className="table-wrap console-table" tabIndex={0} role="region" aria-label={t("Proposed plan", "建議方案")}>
            <table>
              <thead>
                <tr>
                  <th scope="col">ULD</th>
                  <th scope="col">{t("Cargo", "貨類")}</th>
                  <th scope="col">{t("Assigned to", "分配至")}</th>
                  <th scope="col" title={t("Extra weighted delay if this ULD misses its assigned cutoff", "若此 ULD 錯過已分配航班截載所增加的加權延誤")}>
                    R-VaR
                  </th>
                  <th scope="col">{t("Status", "狀態")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.id} className={r.id === current?.id ? "selected" : undefined}>
                    <td>
                      <button type="button" className="row-button" onClick={() => setSelected(r.id)} aria-pressed={r.id === current?.id}>
                        {r.unit.uld_code} · {r.unit.uld_type}
                      </button>
                    </td>
                    <td>{r.unit.service_class.toLowerCase()}</td>
                    <td>
                      {r.flight ? (
                        <>
                          {r.flight.origin}→{r.unit.destination} · {r.flight.flight_number}{" "}
                          <span className="muted">+{fmt(h(r.flight.departure_at))}h</span>
                          {r.assignment && r.assignment.legs.length > 1 ? (
                            <span className="muted"> · {r.assignment.legs.length} {t("legs", "航段")}</span>
                          ) : null}
                        </>
                      ) : (
                        <span className="muted">— {t("no compliant path", "無合規路徑")}</span>
                      )}
                    </td>
                    <td className={`numeric ${r.rvar === null || (r.rvar ?? 0) >= 10 ? "danger-text" : ""}`}>
                      {r.rvar === undefined ? "—" : r.rvar === null ? t("LOST", "失去") : `+${fmt(r.rvar)}`}
                    </td>
                    <td>
                      <span className={`status-chip ${r.status.toLowerCase()}`}>{statusLabel[r.status]}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="console-foot">
            {rows.length > 12 ? (
              <button type="button" className="button quiet" onClick={() => setAll((v) => !v)}>
                {all ? t("Show top 12", "只顯示前 12 項") : t(`+ ${rows.length - 12} more`, `+ 另外 ${rows.length - 12} 項`)}
              </button>
            ) : null}
            <span className="muted">
              {t(
                "Sorted by R-VaR — review the riskiest changes first. R-VaR assumes the snapshot's evidence stays valid; refresh the snapshot before acting later.",
                "按 R-VaR 由高至低排序 — 先審閱風險最高的變更。R-VaR 假設快照證據維持有效；較後行動前須更新快照。",
              )}
            </span>
          </div>
        </section>

        <aside className="console-col" aria-label={t("Explanation", "解釋")}>
          {current ? (
            <Why row={current} candidates={candidates.data} planId={id} h={h} fmt={fmt} flights={flights} />
          ) : null}
        </aside>
      </div>

      <section className="panel">
        <div className="section-heading">
          <h2>{t("CargoPulse vs simple rules on the same snapshot", "相同快照下 CargoPulse 對比簡單規則")}</h2>
          <span>{policyLabel("HiGHS", t)}</span>
        </div>
        {alternatives.loading ? <Loading /> : <PolicyComparison plan={record} alternatives={alternatives.data?.items || []} />}
      </section>
      <section className="panel">
        <div className="section-heading">
          <h2>{t("Flight timeline", "航班時間軸")}</h2>
        </div>
        <FlightTimeline snapshot={snap} assignments={record.plan.assignments} />
      </section>
    </div>
  );
}

function Why({
  row,
  candidates,
  planId,
  h,
  fmt,
  flights,
}: {
  row: Row;
  candidates?: Model<"CandidateSet">;
  planId: string;
  h: (iso: string) => number;
  fmt: (n: number, d?: number) => string;
  flights: Map<string, Model<"FlightCapacity">>;
}) {
  const { t } = useLocale();
  const paths = (candidates?.paths || []).filter((p) => p.cargo_unit_id === row.id);
  const excluded = (candidates?.excluded || []).filter((e) => e.cargo_unit_id === row.id);
  const reasons = new Map<string, number>();
  for (const e of excluded) for (const r of e.reason_codes) reasons.set(`${e.gate} · ${r}`, (reasons.get(`${e.gate} · ${r}`) || 0) + 1);
  const chosen = row.assignment ? paths.find((p) => p.id === row.assignment!.path_id) : undefined;
  const chosenCost = row.assignment ? Number(row.assignment.weighted_delay_hours) : 0;
  // Alternatives are other *flights*, not other positions on the same flight.
  const chosenFlight = row.assignment?.legs[0]?.flight_id;
  const otherFlights = new Map<string, number>();
  for (const p of paths) {
    const f = p.legs[0]?.flight_id;
    if (!f || f === chosenFlight) continue;
    otherFlights.set(f, Math.min(otherFlights.get(f) ?? Infinity, Number(p.weighted_delay_hours)));
  }
  const bestOther = [...otherFlights.entries()].toSorted((a, b) => a[1] - b[1])[0];
  const best = paths.length ? Math.min(...paths.map((p) => Number(p.weighted_delay_hours))) : null;
  const target = row.flight ? `${row.flight.flight_number} +${fmt(h(row.flight.departure_at))}h` : t("escalation", "上報");
  return (
    <div className="why">
      <h2>
        {t("Why", "為何")} {row.unit.uld_code} → {target}?
      </h2>
      {row.assignment && row.flight ? (
        <ul>
          <li>
            <span aria-hidden="true">⏱</span>{" "}
            <strong>
              {t("Cutoff", "截載")} +{fmt(h(row.flight.cutoff_at))}h
            </strong>
            {"; "}
            {!bestOther
              ? t("no other compliant flight — this is the last option.", "沒有其他合規航班 — 這是最後選項。")
              : `${otherFlights.size} ${t("other compliant flight(s); best is", "個其他合規航班；最佳為")} ${flights.get(bestOther[0])?.flight_number ?? bestOther[0]} (${bestOther[1] - chosenCost >= 0 ? "+" : "−"}${fmt(Math.abs(bestOther[1] - chosenCost))} ${t("weighted h vs this flight", "加權小時，對比此航班")}).`}
          </li>
          <li>
            <span aria-hidden="true">✓</span>{" "}
            {row.assignment.reason_codes.includes("GATES_A_TO_H_VERIFIED")
              ? t("Passed gates A–H: safety/DG, ULD contour, capacity, customs, cutoff, cold chain, handling, uniqueness.", "通過關卡 A–H：安全/危險品、ULD 輪廓、運力、海關、截載、冷鏈、人手、不可重複分配。")
              : t("Gate evidence is listed on the decision sheet.", "關卡證據見決策表。")}
          </li>
          {best !== null && chosenCost > best + 1e-9 ? (
            <li>
              <span aria-hidden="true">↔</span>{" "}
              {t(
                `Not on its own fastest flight (+${fmt(chosenCost - best)} weighted h): shared capacity was given to ULDs that lose more by waiting.`,
                `未安排其最快航班（+${fmt(chosenCost - best)} 加權小時）：共用艙位讓給等待代價更高的 ULD。`,
              )}
            </li>
          ) : (
            <li>
              <span aria-hidden="true">↔</span> {t("On its best available flight.", "已安排其最佳可用航班。")}
            </li>
          )}
          <li>
            <span aria-hidden="true">Δ</span> {t("Delay vs commitment", "較承諾延誤")}: {fmt(Number(row.assignment.delay_hours))} h ·{" "}
            {t("weighted", "加權")} {fmt(chosenCost)}
            {chosen ? ` · ${chosen.legs.length} ${t("leg(s)", "航段")}` : ""}
          </li>
        </ul>
      ) : (
        <ul>
          <li>
            <span aria-hidden="true">!</span>{" "}
            {t("No compliant flight within the horizon. CargoPulse escalates instead of forcing an unsafe option.", "時限內沒有合規航班。CargoPulse 會上報，而非塞上不安全選項。")}
          </li>
          <li>
            {t("Reasons", "原因")}: <code>{row.unassigned?.reason_codes.join(" · ")}</code>
          </li>
        </ul>
      )}
      {excluded.length ? (
        <div className="why-excluded">
          <strong>
            {excluded.length} {t("flight options excluded", "個航班選項被剔除")}
          </strong>
          <ul>
            {[...reasons.entries()]
              .toSorted((a, b) => b[1] - a[1])
              .slice(0, 4)
              .map(([r, n]) => (
                <li key={r}>
                  <code>{r}</code> ×{n}
                </li>
              ))}
          </ul>
        </div>
      ) : null}
      <div className="why-actions">
        <Link className="button primary" href={`/plans/${planId}#human-decision`}>
          {t("Review & record decision", "檢視並記錄決策")}
        </Link>
      </div>
      <p className="fine">
        {t(
          "Approve, reject or escalate is recorded on the decision sheet with exact-hash confirmation. Nothing is sent to an airline system.",
          "批准、拒絕或上報須在決策表以完整雜湊確認後記錄。不會傳送至任何航空公司系統。",
        )}
      </p>
    </div>
  );
}
