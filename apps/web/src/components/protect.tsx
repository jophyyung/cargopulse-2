"use client";
import { useState } from "react";
import type { Model } from "@/lib/types";
import { POLICY_COLOR, useTip } from "./charts";
import { useLocale } from "./locale";
import { ErrorNotice, Loading, PageHeader, Section, useResource } from "./ui";

type Result = Model<"ProtectPolicyResult">;
const fmt = (n: number, digits = 0) =>
  n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 });
const COLOR = { PRIORITY_FILL: POLICY_COLOR.PRIORITY_FIRST, CARGOPULSE_LOAD_OPTIMIZER: POLICY_COLOR.HiGHS };

export function ProtectSandbox() {
  const { t } = useLocale();
  const [form, setForm] = useState({ seed: 109, shipments: 45, demand: 1.5 });
  const [query, setQuery] = useState(form);
  const [onlyDiff, setOnlyDiff] = useState(true);
  const data = useResource<Model<"ProtectPlan">>(
    `/protect/sandbox?seed=${query.seed}&shipments=${query.shipments}&demand=${query.demand}`,
  );
  const plan = data.data;
  const opt = plan?.results.find((r) => r.policy === "CARGOPULSE_LOAD_OPTIMIZER");
  const fill = plan?.results.find((r) => r.policy === "PRIORITY_FILL");
  const label = (p: Result["policy"]) =>
    p === "PRIORITY_FILL" ? t("Priority fill", "按優先級組板") : t("CargoPulse load plan", "CargoPulse 組板");
  const booked = plan
    ? {
        kg: plan.shipments.reduce((s, x) => s + x.weight_kg, 0),
        m3: plan.shipments.reduce((s, x) => s + x.volume_m3, 0),
      }
    : null;
  const shipments = plan
    ? plan.shipments.filter((s) => !onlyDiff || s.loaded_optimized !== s.loaded_priority_fill)
    : [];

  return (
    <>
      <PageHeader
        eyebrow={t("PROTECT · PRE-CUTOFF LOAD PLANNING", "PROTECT · 截載前組板")}
        title={t("Same flight, same bookings, better build-up", "同一班機、同一批貨，更好的組板")}
        description={t(
          "Choose which booked shipments fly so that the most shipments by priority are carried, then the most chargeable weight, within payload and volume together.",
          "在業載及容積同時限制下，選出按優先級運載最多貨件、其次計費重量最高的組合。",
        )}
      />
      <div className="notice">
        <strong>{t("Synthetic sandbox", "合成沙盒")}</strong>
        <p>
          {t(
            "One synthetic belly flight with aggregate payload mass and volume only. No hold positions, balance, DG segregation or load-control approval are modelled. Nothing is stored or sent to any airline system.",
            "一班合成客機腹艙航班，只計總業載重量及容積。未模擬艙位、配載平衡、危險品隔離或配載控制審批。不會儲存或傳送至任何航空公司系統。",
          )}
        </p>
      </div>
      <form
        className="toolbar protect-controls"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(form);
        }}
      >
        <label>
          {t("Scenario seed", "情景種子")}
          <input
            type="number"
            min={1}
            max={1000000}
            value={form.seed}
            onChange={(e) => setForm({ ...form, seed: Number(e.target.value) || 1 })}
          />
        </label>
        <label>
          {t("Booked shipments (AWBs)", "已訂艙貨件（AWB）")}
          <input
            type="number"
            min={10}
            max={150}
            value={form.shipments}
            onChange={(e) => setForm({ ...form, shipments: Math.min(150, Math.max(10, Number(e.target.value) || 10)) })}
          />
        </label>
        <label>
          {t("Booked volume ÷ hold volume", "訂艙體積 ÷ 艙容")}
          <input
            type="number"
            min={1}
            max={2.5}
            step={0.1}
            value={form.demand}
            onChange={(e) => setForm({ ...form, demand: Math.min(2.5, Math.max(1, Number(e.target.value) || 1)) })}
          />
        </label>
        <button className="button primary" type="submit">
          {t("Plan this flight", "規劃此航班")}
        </button>
      </form>
      <ErrorNotice error={data.error} />
      {data.loading ? <Loading /> : null}
      {plan && opt && fill && booked ? (
        <>
          <p className="viz-finding">
            {plan.flight_number} · {t("payload", "業載")} {fmt(plan.payload_kg)} kg · {t("hold", "艙容")}{" "}
            {fmt(plan.volume_m3)} m³ · {plan.shipments.length} {t("AWBs booked", "張 AWB 已訂艙")} ({fmt(booked.kg)} kg,{" "}
            {fmt(booked.m3, 1)} m³)
          </p>
          <div className="summary-grid">
            <div>
              <span>{t("Offloaded AWBs", "被甩 AWB")}</span>
              <strong>
                {fill.offloaded_count} → {opt.offloaded_count}
              </strong>
              <small>
                {fill.offloaded_count
                  ? `${fmt(((opt.offloaded_count - fill.offloaded_count) / fill.offloaded_count) * 100)}%`
                  : "—"}{" "}
                {t("vs priority fill", "對比按優先級組板")}
              </small>
            </div>
            <div>
              <span>{t("Chargeable weight carried", "所運計費重量")}</span>
              <strong>
                {opt.chargeable_carried_kg >= fill.chargeable_carried_kg ? "+" : "−"}
                {fmt(Math.abs(opt.chargeable_carried_kg - fill.chargeable_carried_kg))}
                <small> kg</small>
              </strong>
              <small>
                {fmt(fill.chargeable_carried_kg)} → {fmt(opt.chargeable_carried_kg)} kg
              </small>
            </div>
            <div>
              <span>{t("Offloaded priority / express AWBs", "被甩優先 / 特快 AWB")}</span>
              <strong>
                {fill.offloaded_priority_count} → {opt.offloaded_priority_count}
              </strong>
              <small>{t("trade-off shown, not hidden", "取捨如實顯示")}</small>
            </div>
            <div>
              <span>{t("Solver · independent check", "求解器 · 獨立核對")}</span>
              <strong className="status-value">{opt.status}</strong>
              <small>
                {fmt(opt.solve_ms, 0)} ms · {opt.independent_check} / {fill.independent_check}
              </small>
            </div>
          </div>
          <Section title={t("Capacity used on the same flight", "同一航班已用運力")}>
            <UtilisationChart plan={plan} results={[fill, opt]} label={label} />
          </Section>
          <Section title={t("Outcome by policy", "按政策的結果")}>
            <div className="table-wrap" tabIndex={0} role="region" aria-label={t("Outcome by policy", "按政策的結果")}>
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t("Result", "結果")}</th>
                    <th scope="col">{label("PRIORITY_FILL")}</th>
                    <th scope="col">{label("CARGOPULSE_LOAD_OPTIMIZER")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      [t("Loaded AWBs", "已裝 AWB"), (r: Result) => fmt(r.loaded_count)],
                      [t("Offloaded AWBs", "被甩 AWB"), (r: Result) => fmt(r.offloaded_count)],
                      [t("Offloaded weight (kg)", "被甩重量（公斤）"), (r: Result) => fmt(r.offloaded_weight_kg)],
                      [t("Offloaded priority / express AWBs", "被甩優先 / 特快 AWB"), (r: Result) => fmt(r.offloaded_priority_count)],
                      [t("Chargeable weight carried (kg)", "所運計費重量（公斤）"), (r: Result) => fmt(r.chargeable_carried_kg)],
                      [t("Payload used", "已用業載"), (r: Result) => `${fmt(r.weight_utilization * 100, 1)}%`],
                      [t("Volume used", "已用容積"), (r: Result) => `${fmt(r.volume_utilization * 100, 1)}%`],
                      [t("Independent check", "獨立核對"), (r: Result) => `${r.independent_check}${r.check_findings.length ? ` · ${r.check_findings.join(", ")}` : ""}`],
                    ] as [string, (r: Result) => string][]
                  ).map(([name, value]) => (
                    <tr key={name}>
                      <th scope="row">{name}</th>
                      <td className="numeric">{value(fill)}</td>
                      <td className="numeric">
                        <strong>{value(opt)}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
          <Section
            title={t("Shipment decisions", "貨件決定")}
            aside={
              <label className="checkbox">
                <input type="checkbox" checked={onlyDiff} onChange={(e) => setOnlyDiff(e.target.checked)} />
                {t("Only where the plans differ", "只顯示兩個方案不同的貨件")}
              </label>
            }
          >
            <div className="table-wrap" tabIndex={0} role="region" aria-label={t("Shipment decisions", "貨件決定")}>
              <table>
                <thead>
                  <tr>
                    <th scope="col">AWB</th>
                    <th scope="col">{t("Service", "服務")}</th>
                    <th scope="col">kg</th>
                    <th scope="col">m³</th>
                    <th scope="col">{t("Density kg/m³", "密度 公斤/立方米")}</th>
                    <th scope="col">{t("Chargeable kg", "計費公斤")}</th>
                    <th scope="col">{label("PRIORITY_FILL")}</th>
                    <th scope="col">{label("CARGOPULSE_LOAD_OPTIMIZER")}</th>
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((s) => (
                    <tr key={s.id}>
                      <td>{s.id}</td>
                      <td>
                        {s.service_class.toLowerCase()}
                        {s.guaranteed ? ` · ${t("must fly", "必須上機")}` : ""}
                      </td>
                      <td className="numeric">{fmt(s.weight_kg)}</td>
                      <td className="numeric">{fmt(s.volume_m3, 2)}</td>
                      <td className="numeric">{fmt(s.density_kg_m3)}</td>
                      <td className="numeric">{fmt(s.chargeable_kg)}</td>
                      <td>{s.loaded_priority_fill ? t("✓ loaded", "✓ 上機") : t("— offloaded", "— 甩貨")}</td>
                      <td>
                        <strong>{s.loaded_optimized ? t("✓ loaded", "✓ 上機") : t("— offloaded", "— 甩貨")}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!shipments.length ? <p className="muted">{t("Both plans load the same shipments.", "兩個方案裝載相同貨件。")}</p> : null}
          </Section>
          <p className="fine">
            {t(
              `Objective: stage 1 maximises Σ priority weight of loaded AWBs (general 1, priority 2, express 3); stage 2 keeps that and maximises chargeable weight = max(kg, ${plan.volumetric_kg_per_m3} × m³). Constraints: Σ kg ≤ payload, Σ m³ ≤ hold volume, must-fly AWBs loaded. Priority fill loads guaranteed, then higher priority, then booking order, skipping shipments that no longer fit. Exact HiGHS MILP; an independent check re-adds every total.`,
              `目標：第一階段最大化已裝 AWB 的優先級權重總和（一般 1、優先 2、特快 3）；第二階段保持該值並最大化計費重量 = max(公斤, ${plan.volumetric_kg_per_m3} × 立方米)。限制：Σ 公斤 ≤ 業載、Σ 立方米 ≤ 艙容、必須上機貨件須裝載。按優先級組板依次裝載保證艙位、較高優先級、訂艙次序的貨件，裝不下則跳過。以 HiGHS 精確求解，並由獨立核對重新計算總和。`,
            )}
          </p>
        </>
      ) : null}
    </>
  );
}

function UtilisationChart({
  plan,
  results,
  label,
}: {
  plan: Model<"ProtectPlan">;
  results: Result[];
  label: (p: Result["policy"]) => string;
}) {
  const { t } = useLocale();
  const tip = useTip();
  const groups: [string, (r: Result) => number, (r: Result) => string][] = [
    [t("Payload used", "已用業載"), (r) => r.weight_utilization, (r) => `${fmt(r.weight_used_kg)} / ${fmt(plan.payload_kg)} kg`],
    [t("Volume used", "已用容積"), (r) => r.volume_utilization, (r) => `${fmt(r.volume_used_m3, 1)} / ${fmt(plan.volume_m3)} m³`],
  ];
  const W = 1040, left = 210, right = 70, rowH = 26, groupGap = 16;
  const width = W - left - right;
  const height = groups.length * (results.length * rowH + groupGap) + 24;
  return (
    <div className="viz">
      <figure className="viz-figure">
        <svg
          viewBox={`0 0 ${W} ${height}`}
          role="img"
          aria-label={groups
            .map(([g, v]) => `${g}: ${results.map((r) => `${label(r.policy)} ${fmt(v(r) * 100, 1)}%`).join(", ")}`)
            .join("; ")}
        >
          {[0, 0.5, 1].map((p) => (
            <g key={p}>
              <line x1={left + p * width} x2={left + p * width} y1={0} y2={height - 20} className="chart-grid" />
              <text x={left + p * width} y={height - 6} textAnchor="middle" className="chart-label">
                {p * 100}%
              </text>
            </g>
          ))}
          {groups.map(([group, value, detail], gi) =>
            results.map((r, ri) => {
              const y = gi * (results.length * rowH + groupGap) + ri * rowH + 4;
              const v = value(r);
              return (
                <g
                  key={`${group}-${r.policy}`}
                  tabIndex={0}
                  onMouseMove={(e) => tip.show(e, [`${group} · ${label(r.policy)}`, `${fmt(v * 100, 1)}%`, detail(r)])}
                  onFocus={(e) => tip.show(e, [`${group} · ${label(r.policy)}`, `${fmt(v * 100, 1)}%`])}
                  onMouseLeave={tip.hide}
                  onBlur={tip.hide}
                >
                  {ri === 0 ? (
                    <text x={left - 12} y={y + 4} textAnchor="end" className="viz-label strong">
                      {group}
                    </text>
                  ) : null}
                  <text x={left - 12} y={y + 18} textAnchor="end" className="viz-label small">
                    {label(r.policy)}
                  </text>
                  <rect x={left} y={y + 6} width={width} height={16} rx={4} fill="var(--mist)" />
                  <rect x={left} y={y + 6} width={Math.max(2, v * width)} height={16} rx={4} fill={COLOR[r.policy]} />
                  <text x={left + width + 8} y={y + 19} className="viz-value">
                    {fmt(v * 100, 0)}%
                  </text>
                </g>
              );
            }),
          )}
        </svg>
      </figure>
      {tip.view}
    </div>
  );
}
