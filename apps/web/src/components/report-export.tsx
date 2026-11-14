"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { sessionFetch } from "@/lib/session-boundary";
import { useLocale } from "./locale";
import { ErrorNotice } from "./ui";
export function ReportExport({ id }: { id: string }) {
  const { t } = useLocale();
  const [format, setFormat] = useState("json");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  async function download() {
    setBusy(true);
    setError(undefined);
    try {
      const result = await sessionFetch(
        `/api/v1/reports/${encodeURIComponent(id)}/export?format=${format}`,
        { credentials: "same-origin", cache: "no-store" },
      );
      if (!result.ok)
        throw new ApiError(
          result.status,
          await result.json().catch(() => ({ title: "Export unavailable" })),
        );
      const url = URL.createObjectURL(await result.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `cargopulse-synthetic-plan-${id}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="export-controls">
        <label className="sr-only" htmlFor="report-format">
          {t("Report format", "報告格式")}
        </label>
        <select
          id="report-format"
          value={format}
          onChange={(e) => setFormat(e.target.value)}
        >
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
          <option value="pdf">PDF</option>
        </select>
        <button className="quiet" disabled={busy} onClick={download}>
          {busy
            ? t("Exporting…", "正在匯出……")
            : t("Export report", "匯出報告")}
        </button>
      </div>
      <ErrorNotice error={error} />
    </div>
  );
}
