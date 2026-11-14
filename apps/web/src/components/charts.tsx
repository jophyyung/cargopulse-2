"use client";
import { useState } from "react";
import type { Model, Plan, Snapshot } from "@/lib/types";
import { useLocale } from "./locale";

/* Chart colours live in design tokens (globals.css, --viz-*), on the white panel surface:
   policies EF/PF/CP pass all adjacent checks; every bar is also direct-labelled.
   Cargo classes are the reference five (adjacent pass, contrast relief = legend+table). */
export const POLICY_COLOR: Record<string, string> = {
  EARLIEST_FEASIBLE: "var(--viz-policy-earliest)",
  PRIORITY_FIRST: "var(--viz-policy-priority)",
  HiGHS: "var(--viz-policy-optimiser)",
};
export const CLASS_ORDER = ["GENERAL", "PRIORITY", "PHARMA", "PERISHABLE", "DG"] as const;
export const CLASS_COLOR: Record<string, string> = {
  GENERAL: "var(--viz-class-general)",
  PRIORITY: "var(--viz-class-priority)",
  PHARMA: "var(--viz-class-pharma)",
  PERISHABLE: "var(--viz-class-perishable)",
  DG: "var(--viz-class-dg)",
};
// Sequential single-hue ramp (light -> dark) for "extra weighted hours if you wait".
const RAMP = ["var(--viz-ramp-1)", "var(--viz-ramp-2)", "var(--viz-ramp-3)", "var(--viz-ramp-4)", "var(--viz-ramp-5)"];
const ZERO = "var(--viz-zero)";

type Tip = { x: number; y: number; lines: string[] } | null;
export function useTip() {
  const [tip, setTip] = useState<Tip>(null);
  const show = (e: React.MouseEvent | React.FocusEvent, lines: string[]) => {
    const host = (e.currentTarget as Element).closest(".viz");
    const box = host?.getBoundingClientRect();
    const r = (e.currentTarget as Element).getBoundingClientRect();
    const mx = "clientX" in e ? e.clientX : r.left + r.width / 2;
    const my = "clientY" in e ? e.clientY : r.top;
    setTip({ x: mx - (box?.left ?? 0), y: my - (box?.top ?? 0), lines });
  };
  const view = tip ? (
    <div className="viz-tip" style={{ left: tip.x + 14, top: tip.y + 12 }} role="status">
      {tip.lines.map((l, i) => (
        <div key={i} className={i === 0 ? "viz-tip-title" : undefined}>
          {l}
        </div>
      ))}
    </div>
  ) : null;
  return { show, hide: () => setTip(null), view };
}

export function policyLabel(engine: string, t: (en: string, zh: string) => string) {
  if (engine === "HiGHS") return t("CargoPulse (network MILP)", "CargoPulse（網絡 MILP）");
  if (engine === "PRIORITY_FIRST") return t("Priority first", "優先級先行");
  return t("Earliest feasible", "最早可行航班");
}
const fmt = (n: number, digits = 1) =>
  n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });
const hoursFrom = (iso: string, origin: number) => (Date.parse(iso) - origin) / 3_600_000;

/* ---------- 1. Same-snapshot policy comparison ---------- */
export function PolicyComparison({ plan, alternatives }: { plan: Plan; alternatives: Plan[] }) {
  const { t } = useLocale();
  const tip = useTip();
  const order = ["EARLIEST_FEASIBLE", "PRIORITY_FIRST", "HiGHS"];
  const records = [plan, ...alternatives]
    .filter((r, i, all) => all.findIndex((o) => o.plan.solver.engine === r.plan.solver.engine) === i)
    .toSorted((a, b) => order.indexOf(a.plan.solver.engine) - order.indexOf(b.plan.solver.engine));
  const total = plan.plan.assignments.length + plan.plan.unassigned.length;
  const rows = records.map((r) => ({
    engine: r.plan.solver.engine,
    cost: r.plan.solver.objective_value === null ? null : Number(r.plan.solver.objective_value),
    assigned: r.plan.assignments.length,
    ms: Number(r.plan.solver.wall_time_ms),
  }));
  const ours = rows.find((r) => r.engine === "HiGHS");
  const finding = rows
    .filter((r) => r.engine !== "HiGHS" && r.cost && ours?.cost !== null && ours?.cost !== undefined)
    .map((r) => {
      const change = ((ours!.cost! - r.cost!) / r.cost!) * 100;
      return `${change <= 0 ? "−" : "+"}${fmt(Math.abs(change))}% ${t("vs", "對比")} ${policyLabel(r.engine, t)}`;
    });
  if (rows.length < 2)
    return (
      <p className="muted">
        {t(
          "Reference plans are not available for this proposal, so no comparison is drawn.",
          "此建議方案沒有參考方案，因此不繪製比較。",
        )}
      </p>
    );
  const chart = (
    title: string,
    key: "cost" | "assigned",
    unit: string,
    better: string,
    max: number,
  ) => {
    const W = 520, left = 160, right = 64, rowH = 30, top = 8;
    const width = W - left - right;
    return (
      <figure className="viz-figure">
        <figcaption>
          <strong>{title}</strong> <span className="muted">· {better}</span>
        </figcaption>
        <svg
          viewBox={`0 0 ${W} ${top + rows.length * rowH + 22}`}
          role="img"
          aria-label={`${title}: ${rows
            .map((r) => `${policyLabel(r.engine, t)} ${r[key] ?? "—"} ${unit}`)
            .join("; ")}`}
        >
          <line x1={left} x2={left} y1={top - 4} y2={top + rows.length * rowH} className="chart-axis" />
          {rows.map((r, i) => {
            const v = r[key];
            const w = v === null ? 0 : Math.max(2, (v / (max || 1)) * width);
            const y = top + i * rowH + 6;
            return (
              <g
                key={r.engine}
                tabIndex={0}
                onMouseMove={(e) =>
                  tip.show(e, [
                    policyLabel(r.engine, t),
                    `${title}: ${v === null ? "—" : fmt(v)} ${unit}`,
                    `${t("Measured solve time", "實測求解時間")}: ${fmt(r.ms, 0)} ms`,
                  ])
                }
                onFocus={(e) => tip.show(e, [policyLabel(r.engine, t), `${v ?? "—"} ${unit}`])}
                onMouseLeave={tip.hide}
                onBlur={tip.hide}
              >
                <text x={left - 10} y={y + 12} textAnchor="end" className="viz-label">
                  {policyLabel(r.engine, t)}
                </text>
                <rect x={left} y={y} width={w} height={18} rx={4} fill={POLICY_COLOR[r.engine]} />
                <rect x={left} y={y - 4} width={width + right} height={26} fill="transparent" />
                <text x={left + w + 8} y={y + 13} className="viz-value">
                  {v === null ? "—" : fmt(v)}
                </text>
              </g>
            );
          })}
          <text x={left} y={top + rows.length * rowH + 16} className="chart-label">
            0
          </text>
          <text x={left + width} y={top + rows.length * rowH + 16} textAnchor="end" className="chart-label">
            {fmt(max)} {unit}
          </text>
        </svg>
      </figure>
    );
  };
  const maxCost = Math.max(...rows.map((r) => r.cost ?? 0));
  return (
    <div className="viz">
      <p className="viz-finding">
        {finding.length && ours?.cost !== null
          ? `${t("Total plan cost on this snapshot", "此快照的方案總成本")}: ${finding.join(" · ")}`
          : t("Comparison values are incomplete for this run.", "此運行的比較數值不完整。")}
      </p>
      <div className="viz-pair">
        {chart(
          t("Total plan cost", "方案總成本"),
          "cost",
          t("weighted h", "加權小時"),
          t("lower is better · delay + handling + unassigned penalty", "越低越好 · 延誤＋處理＋未分配懲罰"),
          maxCost,
        )}
        {chart(
          t("ULDs given a compliant flight", "獲分配合規航班的 ULD"),
          "assigned",
          `/ ${total}`,
          t("higher is better", "越高越好"),
          total,
        )}
      </div>
      <p className="fine">
        {t(
          "All three policies use the same snapshot, the same gates A–H and the same capacities. The references are transparent rules, not an airline's current process.",
          "三種政策使用相同快照、相同關卡 A–H 及相同運力。參考規則是透明的對照規則，並非航空公司現行流程。",
        )}
      </p>
      {tip.view}
    </div>
  );
}

/* ---------- 2. Urgency heatmap (R-VaR cliff) ---------- */
export type UnitInfo = Pick<Model<"CargoUnit">, "id" | "uld_code" | "service_class" | "destination">;
export function urgencySummary(points: Model<"UrgencyPoint">[], asOf: string) {
  const origin = Date.parse(asOf);
  const byUnit = new Map<string, Model<"UrgencyPoint">[]>();
  for (const p of points) byUnit.set(p.cargo_unit_id, [...(byUnit.get(p.cargo_unit_id) || []), p]);
  const rows = [...byUnit.entries()].map(([id, list]) => {
    const sorted = list.toSorted((a, b) => Date.parse(a.decision_at) - Date.parse(b.decision_at));
    let previous: number | null = 0;
    let cliff: Model<"UrgencyPoint"> | undefined;
    let biggest = 0;
    // Cliff = biggest finite step-up; losing every path is reported separately (lostHours).
    for (const p of sorted) {
      const v = p.delta_weighted_hours === null ? null : Number(p.delta_weighted_hours);
      const jump = v === null || previous === null ? 0 : v - previous;
      if (jump > biggest) {
        biggest = jump;
        cliff = p;
      }
      previous = v;
    }
    cliff ||= sorted.find((p) => p.delta_weighted_hours === null);
    const numeric = sorted.filter((p) => p.delta_weighted_hours !== null).map((p) => Number(p.delta_weighted_hours));
    const lost = sorted.find((p) => p.delta_weighted_hours === null);
    return {
      id,
      points: sorted,
      cliffHours: cliff ? hoursFrom(cliff.decision_at, origin) : null,
      lostHours: lost ? hoursFrom(lost.decision_at, origin) : null,
      max: numeric.length ? Math.max(...numeric) : 0,
      initiallyLost: sorted[0]?.delta_weighted_hours === null,
    };
  });
  return rows.toSorted(
    (a, b) => (a.cliffHours ?? 1e9) - (b.cliffHours ?? 1e9) || b.max - a.max || a.id.localeCompare(b.id),
  );
}

export function UrgencyHeatmap({
  points,
  units,
  asOf,
  validUntil,
}: {
  points: Model<"UrgencyPoint">[];
  units: UnitInfo[];
  asOf: string;
  validUntil?: string;
}) {
  const { t } = useLocale();
  const tip = useTip();
  const [all, setAll] = useState(false);
  const [table, setTable] = useState(false);
  const origin = Date.parse(asOf);
  const info = new Map(units.map((u) => [u.id, u]));
  const rows = urgencySummary(points, asOf).filter((r) => !r.initiallyLost);
  const times = [...new Set(points.map((p) => p.decision_at))].toSorted((a, b) => Date.parse(a) - Date.parse(b));
  if (!rows.length || times.length < 2) return null;
  const horizon = Math.min(48, Math.max(12, hoursFrom(times.at(-1)!, origin) + 1));
  const shown = all ? rows : rows.slice(0, 16);
  const max = Math.max(...rows.map((r) => r.max), 1);
  const color = (v: number) => (v <= 0 ? ZERO : RAMP[Math.min(RAMP.length - 1, Math.floor((v / max) * RAMP.length))]);
  const W = 680, left = 176, right = 70, top = 44, rowH = 18;
  const width = W - left - right;
  const x = (h: number) => left + (Math.min(Math.max(h, 0), horizon) / horizon) * width;
  const within12 = rows.filter((r) => r.cliffHours !== null && r.cliffHours <= 12).length;
  const within2 = rows.filter((r) => r.cliffHours !== null && r.cliffHours <= 2).length;
  const lost12 = rows.filter((r) => r.lostHours !== null && r.lostHours <= 12).length;
  const label = (id: string) => {
    const u = info.get(id);
    return u ? `${u.uld_code} · ${u.service_class.toLowerCase()} → ${u.destination}` : id;
  };
  const ticks = Array.from({ length: Math.floor(horizon / 6) + 1 }, (_, i) => i * 6);
  const expiry = validUntil ? hoursFrom(validUntil, origin) : null;
  return (
    <div className="viz">
      <div className="viz-kpis">
        <div>
          <strong>
            {within12}
            <small> / {rows.length}</small>
          </strong>
          <span>{t("ULDs hit a cliff within 12 h", "個 ULD 在 12 小時內遇上斷崖")}</span>
        </div>
        <div>
          <strong>{within2}</strong>
          <span>{t("must be decided within 2 h", "個須在 2 小時內決定")}</span>
        </div>
        <div>
          <strong>{lost12}</strong>
          <span>{t("lose every compliant path within 12 h", "個在 12 小時內失去所有合規路徑")}</span>
        </div>
      </div>
      <figure className="viz-figure">
        <figcaption>
          <strong>
            {t(
              "Extra weighted delay if each ULD's decision waits (label = cliff time)",
              "若延遲每個 ULD 的決定所增加的加權延誤（標籤 = 斷崖時間）",
            )}
          </strong>
          <br />
          <span className="muted">
            {t(
              "What-if: route evidence as of the snapshot is assumed to stay valid, so only cutoffs and connections close options. Refresh the snapshot before acting on a later time.",
              "假設情境：快照時的路線證據維持有效，只有截載及轉駁會令選項消失。在較後時間行動前須更新快照。",
            )}
          </span>
        </figcaption>
        <svg
          viewBox={`0 0 ${W} ${top + shown.length * rowH + 34}`}
          role="img"
          aria-label={t(
            `Urgency heatmap for ${shown.length} ULDs; ${within12} reach a cliff within 12 hours. A data table is available below.`,
            `${shown.length} 個 ULD 的緊急程度熱圖；${within12} 個在 12 小時內遇上斷崖。下方提供數據表。`,
          )}
        >
          <defs>
            <pattern id="nopath" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--block-tint)" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="var(--block)" strokeWidth="2" />
            </pattern>
          </defs>
          {ticks.map((h) => (
            <g key={h}>
              <line x1={x(h)} x2={x(h)} y1={top - 6} y2={top + shown.length * rowH} className="chart-grid" />
              <text x={x(h)} y={top - 10} textAnchor="middle" className="chart-label">
                +{h}h
              </text>
            </g>
          ))}
          {expiry !== null && expiry < horizon ? (
            <g>
              <line x1={x(expiry)} x2={x(expiry)} y1={top - 34} y2={top + shown.length * rowH} className="viz-expiry" />
              <text x={x(expiry) + 4} y={top - 24} className="chart-label">
                {t("snapshot expires", "快照到期")}
              </text>
            </g>
          ) : null}
          {shown.map((r, i) => {
            const y = top + i * rowH;
            return (
              <g key={r.id}>
                <text x={left - 8} y={y + 12.5} textAnchor="end" className="viz-label small">
                  {label(r.id)}
                </text>
                {r.points.map((p, j) => {
                  const same = (a?: Model<"UrgencyPoint">) => a && a.delta_weighted_hours === p.delta_weighted_hours;
                  if (j > 0 && same(r.points[j - 1])) return null; // merged into the run's first cell
                  let k = j + 1;
                  while (k < r.points.length && same(r.points[k])) k++;
                  const h0 = hoursFrom(p.decision_at, origin);
                  const next = r.points[k];
                  const h1 = next ? hoursFrom(next.decision_at, origin) : horizon;
                  if (h0 >= horizon) return null;
                  const nul = p.delta_weighted_hours === null;
                  const v = nul ? 0 : Number(p.delta_weighted_hours);
                  const cx = x(h0), cw = Math.max(1, x(h1) - x(h0));
                  return (
                    <rect
                      key={p.decision_at}
                      x={cx}
                      y={y + 1}
                      width={cw}
                      height={rowH - 2}
                      fill={nul ? "url(#nopath)" : color(v)}
                      onMouseMove={(e) =>
                        tip.show(e, [
                          label(r.id),
                          `${t("Decide at", "決定時間")} +${fmt(h0)}h`,
                          nul
                            ? t("No compliant path remains — escalate", "已無合規路徑 — 須上報")
                            : `Δ ${fmt(v)} ${t("weighted h", "加權小時")}`,
                        ])
                      }
                      onMouseLeave={tip.hide}
                    />
                  );
                })}
                <text x={W - right + 8} y={y + 12.5} className="viz-value small">
                  {r.cliffHours === null
                    ? t("no cliff", "無斷崖")
                    : `${r.lostHours !== null && r.lostHours === r.cliffHours ? "× " : ""}+${fmt(r.cliffHours)}h`}
                </text>
              </g>
            );
          })}
          <g transform={`translate(${left}, ${top + shown.length * rowH + 14})`}>
            <rect width="14" height="10" fill={ZERO} stroke="var(--hairline-strong)" />
            <text x="18" y="9" className="chart-label">0</text>
            {RAMP.map((c, i) => (
              <rect key={c} x={34 + i * 22} width="22" height="10" fill={c} />
            ))}
            <text x={34 + RAMP.length * 22 + 4} y="9" className="chart-label">
              {fmt(max)} {t("weighted h", "加權小時")}
            </text>
            <rect x="250" width="14" height="10" fill="url(#nopath)" />
            <text x="268" y="9" className="chart-label">
              × {t("no compliant path", "無合規路徑")}
            </text>
          </g>
        </svg>
      </figure>
      <div className="viz-actions">
        {rows.length > 16 ? (
          <button type="button" className="button quiet" onClick={() => setAll((v) => !v)}>
            {all ? t("Show the 16 most urgent", "只顯示最緊急 16 個") : t(`Show all ${rows.length} ULDs`, `顯示全部 ${rows.length} 個 ULD`)}
          </button>
        ) : null}
        <button type="button" className="button quiet" onClick={() => setTable((v) => !v)} aria-expanded={table}>
          {table ? t("Hide data table", "隱藏數據表") : t("Show data table", "顯示數據表")}
        </button>
      </div>
      {table ? (
        <div className="table-wrap viz-table" tabIndex={0} role="region" aria-label={t("Urgency data", "緊急程度數據")}>
          <table>
            <thead>
              <tr>
                <th scope="col">ULD</th>
                <th scope="col">{t("Cliff", "斷崖")}</th>
                <th scope="col">{t("All paths lost", "失去所有路徑")}</th>
                <th scope="col">{t("Max Δ weighted h", "最大 Δ 加權小時")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{label(r.id)}</td>
                  <td>{r.cliffHours === null ? "—" : `+${fmt(r.cliffHours)}h`}</td>
                  <td>{r.lostHours === null ? "—" : `+${fmt(r.lostHours)}h`}</td>
                  <td className="numeric">{fmt(r.max)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tip.view}
    </div>
  );
}

/* ---------- 3. Flight timeline with per-class load ---------- */
export function FlightTimeline({ snapshot, assignments }: { snapshot: Snapshot; assignments: Model<"Assignment">[] }) {
  const { t } = useLocale();
  const tip = useTip();
  const [table, setTable] = useState(false);
  const origin = Date.parse(snapshot.as_of);
  const units = new Map(snapshot.cargo_units.map((u) => [u.id, u]));
  const load = new Map<string, Record<string, { kg: number; n: number }>>();
  for (const a of assignments) {
    const u = units.get(a.cargo_unit_id);
    if (!u) continue;
    for (const leg of a.legs) {
      const entry = load.get(leg.flight_id) || {};
      const c = (entry[u.service_class] ||= { kg: 0, n: 0 });
      c.kg += Number(u.actual_mass_kg);
      c.n += 1;
      load.set(leg.flight_id, entry);
    }
  }
  const capacity = (f: Snapshot["flights"][number]) =>
    f.free_mass_kg !== null
      ? Number(f.free_mass_kg)
      : f.positions.reduce((s, p) => s + Number(p.free_mass_kg ?? 0), 0);
  const flights = snapshot.flights
    .filter((f) => hoursFrom(f.departure_at, origin) <= 48 && hoursFrom(f.departure_at, origin) >= -2)
    .toSorted((a, b) => Date.parse(a.departure_at) - Date.parse(b.departure_at));
  const routes = [...new Set(flights.map((f) => `${f.origin}→${f.destination}`))].toSorted();
  if (!flights.length) return null;
  const horizon = Math.min(48, Math.max(12, Math.ceil(Math.max(...flights.map((f) => hoursFrom(f.departure_at, origin))) / 6) * 6 + 2));
  const W = 1060, left = 92, right = 24, top = 26, rowH = 36, blockW = 34;
  const width = W - left - right - blockW;
  const x = (h: number) => left + (Math.max(0, h) / horizon) * width;
  const ticks = Array.from({ length: Math.floor(horizon / 6) + 1 }, (_, i) => i * 6);
  const used = (id: string) => Object.values(load.get(id) || {}).reduce((s, c) => s + c.kg, 0);
  const assignedFlights = flights.filter((f) => load.has(f.id)).length;
  return (
    <div className="viz">
      <p className="viz-finding">
        {t(
          `${assignments.length} ULDs assigned across ${assignedFlights} of ${flights.length} flights in the next ${horizon} h.`,
          `未來 ${horizon} 小時內，${assignments.length} 個 ULD 分配至 ${flights.length} 班航班中的 ${assignedFlights} 班。`,
        )}
      </p>
      <figure className="viz-figure">
        <figcaption>
          <strong>{t("Proposed plan on the flight timeline", "建議方案的航班時間軸")}</strong>{" "}
          <span className="muted">
            · {t("block = flight at departure; fill = assigned mass ÷ free capacity, by cargo class", "方塊 = 起飛時的航班；填色 = 已分配重量 ÷ 可用運力，按貨類")}
          </span>
        </figcaption>
        <svg
          viewBox={`0 0 ${W} ${top + routes.length * rowH + 10}`}
          role="img"
          aria-label={t(
            `Flight timeline: ${flights.length} flights on ${routes.length} routes, ${assignedFlights} carrying proposed ULDs. A data table is available below.`,
            `航班時間軸：${routes.length} 條航線共 ${flights.length} 班航班，其中 ${assignedFlights} 班載有建議分配的 ULD。下方提供數據表。`,
          )}
        >
          <defs>
            <pattern id="cancelled" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--mist)" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="var(--line-strong)" strokeWidth="1.5" />
            </pattern>
          </defs>
          {ticks.map((h) => (
            <g key={h}>
              <line x1={x(h)} x2={x(h)} y1={top - 6} y2={top + routes.length * rowH} className="chart-grid" />
              <text x={x(h)} y={top - 10} textAnchor="middle" className="chart-label">
                {h === 0 ? t("now", "現在") : `+${h}h`}
              </text>
            </g>
          ))}
          {routes.map((route, i) => (
            <text key={route} x={left - 10} y={top + i * rowH + rowH / 2 + 4} textAnchor="end" className="viz-label">
              {route}
            </text>
          ))}
          {flights.map((f) => {
            const row = routes.indexOf(`${f.origin}→${f.destination}`);
            const bx = x(hoursFrom(f.departure_at, origin));
            const by = top + row * rowH + 5;
            const bh = rowH - 10;
            const cap = capacity(f);
            const classes = load.get(f.id) || {};
            const cancelled = f.status === "CANCELLED";
            let cursor = by + bh;
            const segments = CLASS_ORDER.filter((c) => classes[c]).map((c) => {
              const h = cap > 0 ? Math.max(2, (classes[c]!.kg / cap) * bh) : 0;
              const seg = { c, y: Math.max(by, cursor - h), h: Math.min(h, cursor - by) };
              cursor = seg.y - (h > 0 ? 1 : 0);
              return seg;
            });
            const pct = cap > 0 ? Math.round((used(f.id) / cap) * 100) : null;
            return (
              <g
                key={f.id}
                tabIndex={0}
                onMouseMove={(e) =>
                  tip.show(e, [
                    `${f.flight_number} · ${f.origin}→${f.destination}${f.is_freighter ? ` · ${t("freighter", "貨機")}` : ""}`,
                    `${t("Departs", "起飛")} +${fmt(hoursFrom(f.departure_at, origin))}h · ${t("cutoff", "截載")} +${fmt(hoursFrom(f.cutoff_at, origin))}h`,
                    cancelled
                      ? t("Cancelled", "已取消")
                      : `${t("Assigned", "已分配")} ${fmt(used(f.id), 0)} / ${fmt(cap, 0)} kg${pct !== null ? ` (${pct}%)` : ""}`,
                    ...CLASS_ORDER.filter((c) => classes[c]).map((c) => `${c.toLowerCase()}: ${classes[c]!.n} ULD`),
                  ])
                }
                onFocus={(e) => tip.show(e, [`${f.flight_number} · ${f.origin}→${f.destination}`])}
                onMouseLeave={tip.hide}
                onBlur={tip.hide}
              >
                <rect
                  x={bx}
                  y={by}
                  width={blockW}
                  height={bh}
                  rx={3}
                  fill={cancelled ? "url(#cancelled)" : "var(--paper)"}
                  stroke={f.is_freighter ? "var(--pine)" : "var(--line-strong)"}
                  strokeWidth={f.is_freighter ? 2 : 1}
                />
                {segments.map((s) => (
                  <rect key={s.c} x={bx + 3} y={s.y} width={blockW - 6} height={Math.max(0, s.h)} fill={CLASS_COLOR[s.c]} />
                ))}
              </g>
            );
          })}
        </svg>
        <div className="viz-legend">
          {CLASS_ORDER.map((c) => (
            <span key={c}>
              <i style={{ background: CLASS_COLOR[c] }} />
              {c.toLowerCase()}
            </span>
          ))}
          <span>
            <i className="outline-thick" />
            {t("freighter", "貨機")}
          </span>
          <span>
            <i className="hatched" />
            {t("cancelled", "已取消")}
          </span>
        </div>
      </figure>
      <div className="viz-actions">
        <button type="button" className="button quiet" onClick={() => setTable((v) => !v)} aria-expanded={table}>
          {table ? t("Hide data table", "隱藏數據表") : t("Show data table", "顯示數據表")}
        </button>
      </div>
      {table ? (
        <div className="table-wrap viz-table" tabIndex={0} role="region" aria-label={t("Flight load data", "航班裝載數據")}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t("Flight", "航班")}</th>
                <th scope="col">{t("Departs", "起飛")}</th>
                <th scope="col">{t("Assigned ULDs", "已分配 ULD")}</th>
                <th scope="col">{t("Assigned kg / free kg", "已分配公斤 / 可用公斤")}</th>
              </tr>
            </thead>
            <tbody>
              {flights.map((f) => (
                <tr key={f.id}>
                  <td>
                    {f.flight_number} {f.origin}→{f.destination}
                    {f.is_freighter ? ` · ${t("freighter", "貨機")}` : ""}
                    {f.status === "CANCELLED" ? ` · ${t("cancelled", "已取消")}` : ""}
                  </td>
                  <td>+{fmt(hoursFrom(f.departure_at, origin))}h</td>
                  <td className="numeric">{Object.values(load.get(f.id) || {}).reduce((s, c) => s + c.n, 0)}</td>
                  <td className="numeric">
                    {fmt(used(f.id), 0)} / {fmt(capacity(f), 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {tip.view}
    </div>
  );
}
