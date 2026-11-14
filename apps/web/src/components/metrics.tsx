"use client";
import type { Model } from "@/lib/types";
import { useLocale } from "./locale";
import { Badge, Empty, Hash, JsonDetails, Table, Time } from "./ui";
export function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob(
      [
        JSON.stringify(
          {
            export_label: "SYNTHETIC / NOT CONNECTED",
            scope:
              "CargoPulse in-app evidence only; not physical operational outcomes",
            exported_at: new Date().toISOString(),
            data: value,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
export function Metrics({ items }: { items: Model<"MetricValue">[] }) {
  const { t } = useLocale();
  if (!items.length)
    return (
      <Empty>
        {t(
          "No computed metrics are available. No operational performance is inferred.",
          "尚無已計算的指標。不推斷任何實際作業表現。",
        )}
      </Empty>
    );
  function label(name: string) {
    if (name.toLowerCase() === "proposed_departure_48h_eligible_uld_rate")
      return t(
        "Proposed departure within 48 h · eligible ULDs",
        "48 小時內建議起飛 · 符合資格 ULD",
      );
    if (name.toLowerCase() === "proposed_departure_48h_all_affected_uld_rate")
      return t(
        "Proposed departure within 48 h · all affected ULDs",
        "48 小時內建議起飛 · 全部受影響 ULD",
      );
    return name.replaceAll("_", " ");
  }
  return (
    <>
      <Table
        caption={t(
          "Evidence-bound metrics with exact denominators",
          "附精確分母的證據指標",
        )}
        headers={[
          t("Metric / status", "指標 / 狀態"),
          t("Value / unit", "數值 / 單位"),
          t("Numerator / denominator", "分子 / 分母"),
          t("Cohort / method", "群組 / 方法"),
          t("Evidence", "證據"),
        ]}
      >
        {items.map((m, i) => (
          <tr key={`${m.name}-${i}`}>
            <td>
              <strong>{label(m.name)}</strong>
              <small>
                <Badge value={m.status} />
              </small>
              <small>{m.statistic}</small>
            </td>
            <td className="numeric">
              {m.value ?? t("Undefined", "未定義")}
              <small>{m.unit}</small>
            </td>
            <td>
              {m.numerator ?? "—"} / {m.denominator ?? "—"}
              <small>{m.baseline_policy_version}</small>
            </td>
            <td>
              {m.cohort_id}
              <small>{m.metric_method_version}</small>
              <small>
                <Time value={m.window_start_utc} /> →{" "}
                <Time value={m.window_end_utc} />
              </small>
            </td>
            <td>
              <span>{m.evidence_tier}</span>
              <small>{m.data_source_ids.join(", ")}</small>
              <details>
                <summary>{t("Provenance", "來源證據")}</summary>
                <p>
                  {t("Input as of", "輸入時間")}:{" "}
                  <Time value={m.event_as_of_utc} />
                </p>
                <Hash value={m.snapshot_hash} />
                <Hash value={m.policy_hash} />
              </details>
            </td>
          </tr>
        ))}
      </Table>
      <p className="fine">
        {t(
          "Proposed departure within 48 h describes the first proposed flight departure, not physical arrival or confirmed re-protection. Eligible and all-affected ULDs are separate denominators. A zero denominator remains undefined. Weighted hours are not elapsed hours or revenue.",
          "48 小時內建議起飛指第一程建議航班的起飛時間，並非實體抵達或已確認重新安排。符合資格與全部受影響 ULD 的分母分開計算。分母為零時維持未定義。加權時數不等於實際經過時數或收入。",
        )}
      </p>
      <JsonDetails
        value={items}
        label={t(
          "Full metric definitions and provenance",
          "完整指標定義及來源證據",
        )}
      />
    </>
  );
}
