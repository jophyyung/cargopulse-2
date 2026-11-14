"use client";
import { useState } from "react";
import type { Model } from "@/lib/types";
import { UrgencyHeatmap, type UnitInfo } from "./charts";
import { useLocale } from "./locale";
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  Section,
  Table,
  Time,
  useResource,
} from "./ui";
export function Urgency({
  scenarioId,
  cargoUnits = [],
  asOf,
  validUntil,
}: {
  scenarioId: string;
  cargoUnits?: UnitInfo[];
  asOf?: string;
  validUntil?: string;
}) {
  const { t } = useLocale();
  const data = useResource<Model<"UrgencyPoint">[]>(
    `/scenarios/${scenarioId}/urgency`,
  );
  const hold = useResource<Model<"UrgencyPoint">[]>(
    asOf && !data.loading ? `/scenarios/${scenarioId}/urgency?evidence=hold` : null,
  );
  const [selected, setSelected] = useState("");
  const units = [...new Set(data.data?.map((p) => p.cargo_unit_id) || [])];
  const unit = units.includes(selected) ? selected : units[0];
  const points = (data.data || [])
    .filter((p) => p.cargo_unit_id === unit)
    .toSorted((a, b) => Date.parse(a.decision_at) - Date.parse(b.decision_at));
  const numbers = points.filter((p) => p.delta_weighted_hours !== null);
  const start = Date.parse(points[0]?.decision_at || "");
  const end = Date.parse(points.at(-1)?.decision_at || "");
  const max = Math.max(
    ...numbers.map((p) => Number(p.delta_weighted_hours)),
    1,
  );
  const x = (p: Model<"UrgencyPoint">) =>
    70 + ((Date.parse(p.decision_at) - start) / (end - start)) * 500;
  const y = (p: Model<"UrgencyPoint">) =>
    210 - (Number(p.delta_weighted_hours) / max) * 155;
  return (
    <Section
      title={t("Urgency / cost of waiting", "緊急程度 / 等待代價")}
      aside={
        units.length ? (
          <label className="inline-label">
            ULD
            <select value={unit} onChange={(e) => setSelected(e.target.value)}>
              {units.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </label>
        ) : null
      }
    >
      <p>
        {t(
          "Server-computed change in weighted delay using the same snapshot. Steps occur when an option becomes unavailable. Null values mean no compliant path; expired source evidence can also close an option. Refresh the snapshot before acting on later times.",
          "伺服器以同一快照計算加權延誤變化；當選項失效時，數值會跳升。空值表示無合規路徑，來源證據過期亦會令選項失效。在較後時間採取行動前，必須更新快照。",
        )}
      </p>
      <ErrorNotice error={data.error} />
      {data.loading ? <Loading /> : null}
      {hold.loading ? (
        <p role="status" className="muted">
          {t("Computing the route-cliff what-if for every ULD (about 20 s the first time)…", "正在為每個 ULD 計算路線斷崖假設情境（首次約 20 秒）……")}
        </p>
      ) : null}
      <ErrorNotice error={hold.error} />
      {hold.data && asOf ? (
        <UrgencyHeatmap points={hold.data} units={cargoUnits} asOf={asOf} validUntil={validUntil} />
      ) : null}
      {points.length && end > start && numbers.length ? (
        <div className="urgency-chart">
          <svg
            viewBox="0 0 620 290"
            role="img"
            aria-label={t(
              `Weighted delay delta for ${unit}; detailed values follow in the table.`,
              `${unit} 的加權延誤差值；詳細數值見下表。`,
            )}
          >
            <text x="70" y="23" className="chart-label">
              {t("Δ weighted hours · single ULD", "Δ 加權時數 · 單一 ULD")}
            </text>
            {[0, 0.5, 1].map((r) => (
              <g key={r}>
                <line
                  x1="70"
                  x2="570"
                  y1={210 - r * 155}
                  y2={210 - r * 155}
                  className="chart-grid"
                />
                <text
                  x="58"
                  y={214 - r * 155}
                  textAnchor="end"
                  className="chart-label"
                >
                  {(max * r).toFixed(1)}
                </text>
              </g>
            ))}
            <line x1="70" x2="570" y1="210" y2="210" className="chart-axis" />
            {points.map((p, i) => {
              const previous = points[i - 1];
              if (p.delta_weighted_hours === null)
                return (
                  <g key={p.decision_at}>
                    <line
                      x1={x(p)}
                      x2={x(p)}
                      y1="50"
                      y2="210"
                      className="chart-no-path"
                    />
                    <text
                      x={x(p)}
                      y="240"
                      textAnchor="middle"
                      className="chart-label"
                    >
                      ×
                    </text>
                    <title>{p.decision_at}: NO COMPLIANT PATH</title>
                  </g>
                );
              return (
                <g key={p.decision_at}>
                  {previous?.delta_weighted_hours !== null && previous ? (
                    <path
                      d={`M ${x(previous)} ${y(previous)} H ${x(p)} V ${y(p)}`}
                      fill="none"
                      className="chart-series"
                    />
                  ) : null}
                  <circle cx={x(p)} cy={y(p)} r="4" className="chart-point">
                    <title>
                      {p.decision_at}: {p.delta_weighted_hours} weighted h
                    </title>
                  </circle>
                </g>
              );
            })}
            <text x="70" y="265" className="chart-label">
              {new Date(start).toISOString().slice(11, 16)} UTC
            </text>
            <text x="570" y="265" textAnchor="end" className="chart-label">
              {new Date(end).toISOString().slice(11, 16)} UTC
            </text>
          </svg>
        </div>
      ) : null}
      {points.length ? (
        <Table
          caption={t(
            "Computed urgency points for the selected ULD",
            "所選 ULD 的緊急程度計算點",
          )}
          headers={[
            t("Decision time", "決策時間"),
            t("Additional delay", "額外延誤"),
            t("Path status", "路徑狀態"),
            t("Last cutoff", "最後截止時間"),
          ]}
        >
          {points.map((p, i) => (
            <tr key={i}>
              <td>
                <Time value={p.decision_at} />
              </td>
              <td>
                {p.delta_weighted_hours === null
                  ? "—"
                  : `${p.delta_weighted_hours} weighted h`}
              </td>
              <td>
                <Badge value={p.status} />
              </td>
              <td>
                <Time value={p.last_cutoff_at} />
              </td>
            </tr>
          ))}
        </Table>
      ) : !data.loading ? (
        <Empty>
          {t(
            "No computed urgency observations are available. Use the exact flight cutoffs below.",
            "尚無已計算的緊急程度觀測值。請參閱下方精確航班截止時間。",
          )}
        </Empty>
      ) : null}
    </Section>
  );
}
