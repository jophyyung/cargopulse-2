"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Model, Snapshot } from "@/lib/types";
import { useLocale } from "./locale";
import { ErrorNotice } from "./ui";
export function CsvImport({
  enabled,
  snapshotJson,
  onValidated,
}: {
  enabled: boolean;
  snapshotJson: string;
  onValidated: (record: Model<"ImportRecord">) => void;
}) {
  const { t } = useLocale();
  const [metadata, setMetadata] = useState("");
  const [file, setFile] = useState<File>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  function useMetadata() {
    setError(undefined);
    try {
      const snapshot = JSON.parse(snapshotJson) as Snapshot;
      const { cargo_units, ...rest } = snapshot;
      void cargo_units;
      setMetadata(JSON.stringify(rest, null, 2));
    } catch (e) {
      setError(e);
    }
  }
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(undefined);
    setBusy(true);
    try {
      if (file.size > 8 * 1024 * 1024)
        throw new Error(
          t("CSV exceeds the 8 MB limit.", "CSV 超過 8 MB 限制。"),
        );
      if (!file.name.toLowerCase().endsWith(".csv"))
        throw new Error(
          t("Choose a UTF-8 .csv file.", "請選擇 UTF-8 .csv 檔案。"),
        );
      JSON.parse(metadata);
      const body = new FormData();
      body.set("file", new File([file], file.name, { type: "text/csv" }));
      body.set("metadata", metadata);
      onValidated(
        await api<Model<"ImportRecord">>("/imports/upload-csv", {
          method: "POST",
          body,
        }),
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="csv-import">
      <summary>{t("Controlled CSV intake", "受控 CSV 匯入")}</summary>
      <p className="fine">
        {t(
          "UTF-8, 1–1,200 CargoUnit rows, at most 8 MB. Use canonical CargoUnit field names as headers. pieces, serviceability and security are JSON cells; booleans must be true or false. Snapshot metadata contains the full snapshot except cargo_units.",
          "UTF-8、1–1,200 個 CargoUnit 資料列，最多 8 MB。欄位標題須使用標準 CargoUnit 欄位名稱。pieces、serviceability 及 security 為 JSON 儲存格；布林值須為 true 或 false。快照中繼資料包含 cargo_units 以外的完整快照。",
        )}
      </p>
      <button
        className="button"
        type="button"
        onClick={useMetadata}
        disabled={!snapshotJson || busy}
      >
        {t("Use metadata from JSON above", "使用上方 JSON 的中繼資料")}
      </button>
      <form onSubmit={upload}>
        <label>
          {t("Snapshot metadata JSON", "快照中繼資料 JSON")}
          <textarea
            rows={7}
            className="json-input"
            value={metadata}
            maxLength={6000000}
            onChange={(e) => setMetadata(e.target.value)}
            required
            spellCheck={false}
          />
        </label>
        <label>
          {t("Controlled cargo-unit CSV", "受控貨物單位 CSV")}
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0])}
            required
          />
        </label>
        <button
          className="button"
          disabled={!enabled || !metadata || !file || busy}
        >
          {busy
            ? t("Validating upload…", "正在驗證上傳……")
            : t("Upload & validate CSV", "上傳並驗證 CSV")}
        </button>
      </form>
      <ErrorNotice error={error} />
    </details>
  );
}
